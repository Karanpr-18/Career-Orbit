"""
job_hunter.py – Main orchestration script for the AgentScope Multi-Agent Job Hunter.

This script chains four specialized agents together to automate:
  1. Searching for AI/ML internship postings (Scout)
  2. Evaluating and routing jobs (Architect)
  3. Drafting cold emails (Ghostwriter)
  4. Executing applications and tracking results (Dispatcher)

Usage:
  python job_hunter.py              # Normal run (respects 9am-5pm schedule)
  python job_hunter.py --force      # Force run regardless of time
  python job_hunter.py --dry-run    # Dry run – no actual applications or emails
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime

import agentscope
from agentscope.message import Msg

# ── Local imports ──
from config import (
    MODEL_CONFIGS,
    TRACKER_CSV_PATH,
    RESUME_PATH,
    CV_PATH,
    MAX_APPLICATIONS_PER_DAY,
    DELAY_BETWEEN_APPLICATIONS,
    WORK_HOURS_START,
    WORK_HOURS_END,
    SEARCH_QUERIES,
    TARGET_SITES,
    KARAN_PROFILE,
)
from agents import (
    create_scout_agent,
    create_architect_agent,
    create_ghostwriter_agent,
    create_dispatcher_agent,
)
from tools import (
    web_search_jobs,
    scrape_job_page,
    score_job,
    route_action,
    playwright_apply,
    gmail_draft_email,
    append_to_tracker,
    load_existing_urls,
    extract_company_from_url,
    search_hiring_email,
)

# ──────────────────────────────────────────────
# STATUS REPORTING SETUP
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_PATH = os.path.join(BASE_DIR, "agent_status.json")

def write_status(status="running", step="Initializing", done=0, total=50):
    try:
        with open(STATUS_PATH, "w") as f:
            json.dump({
                "status": status,
                "step": step,
                "progress": {"done": done, "total": total},
                "last_update": datetime.now().strftime("%H:%M:%S")
            }, f)
    except Exception as e:
        logger.warning(f"Could not write status: {e}")

# ──────────────────────────────────────────────
# LOGGING SETUP
# ──────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        ),
    ],
)
logger = logging.getLogger("job_hunter")


# ──────────────────────────────────────────────
# HELPER: PARSE JSON FROM LLM RESPONSE
# ──────────────────────────────────────────────
def parse_json_from_response(text: str):
    """
    Extract and parse JSON from an LLM response that may contain markdown
    code fences, extra text, or other wrapping.

    Args:
        text: The raw LLM response string.

    Returns:
        Parsed JSON (dict or list), or None if parsing fails.
    """
    # Strip markdown code fences
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array or object in the text
    for pattern in [
        r"\[[\s\S]*\]",   # JSON array
        r"\{[\s\S]*\}",   # JSON object
    ]:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    logger.warning(f"Could not parse JSON from response: {text[:200]}...")
    return None


# ──────────────────────────────────────────────
# PHASE 1: SCOUT – DISCOVER JOBS
# ──────────────────────────────────────────────
def run_scout_phase(scout_agent, existing_urls: set) -> list[dict]:
    """
    Run the Scout agent to discover new job postings.

    Uses DuckDuckGo search (tool-based) and then asks the Scout LLM
    to evaluate and filter the raw results.

    Args:
        scout_agent: The Scout DialogAgent instance.
        existing_urls: Set of URLs already in the tracker.

    Returns:
        A list of dicts with 'title', 'url', and 'company' for new jobs.
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: THE SCOUT – Discovering new job postings")
    logger.info("=" * 60)
    write_status(step="Searching", done=0)

    all_raw_results = []

    # Step 1: Run web searches for each query + site combination
    for query in SEARCH_QUERIES:
        # Search across all sites
        results = web_search_jobs(query, max_results=30)
        all_raw_results.extend(results)

        # Also search specific target sites
        for site in TARGET_SITES[:8]:  # Increased to top 8 sites
            site_query = f"{query} site:{site}"
            results = web_search_jobs(site_query, max_results=20)
            all_raw_results.extend(results)

    # Step 2: Deduplicate by URL
    seen_urls = set()
    unique_results = []
    for r in all_raw_results:
        url = r.get("url", "")
        if url and url not in seen_urls and url not in existing_urls:
            seen_urls.add(url)
            unique_results.append(r)

    logger.info(f"[Scout] Raw search yielded {len(all_raw_results)} results, "
                f"{len(unique_results)} unique new URLs after dedup")

    if not unique_results:
        logger.info("[Scout] No new job URLs found. Ending scout phase.")
        return []

    # Step 3: Ask the Scout LLM to filter and structure the results in chunks
    filtered_jobs = []
    chunk_size = 20  # Small chunks to stay within 6000 TPM limit
    
    for i in range(0, min(len(unique_results), 100), chunk_size):
        chunk = unique_results[i:i+chunk_size]
        search_summary = json.dumps(chunk, indent=1)
        
        scout_prompt = (
            f"Filter these job postings to ONLY keep AI/ML/Data Science roles suitable for a student or junior (Internships, Junior, Associate). "
            f"Exclude Senior/Lead roles with 3+ years experience. Return a JSON array with 'title', 'url', and 'company'.\n\n"
            f"Results:\n{search_summary}"
        )
        
        try:
            scout_msg = Msg("user", scout_prompt, role="user")
            scout_response = scout_agent(scout_msg)
            chunk_filtered = parse_json_from_response(scout_response.content)
            if chunk_filtered and isinstance(chunk_filtered, list):
                filtered_jobs.extend(chunk_filtered)
            
            # Small delay to avoid hitting TPM rate limits
            time.sleep(2)
        except Exception as e:
            logger.warning(f"[Scout] Chunk filtering failed: {e}")
            continue

    if not filtered_jobs:
        logger.warning("[Scout] No filtered results from LLM. Using raw results as fallback.")
        # Fallback: use raw unique results directly
        filtered_jobs = [
            {
                "title": r.get("title", "Unknown Role"),
                "url": r.get("url", ""),
                "company": extract_company_from_url(r.get("url", "")),
            }
            for r in unique_results[:MAX_APPLICATIONS_PER_DAY]
        ]

    logger.info(f"[Scout] Final filtered job count: {len(filtered_jobs)}")
    return filtered_jobs


# ──────────────────────────────────────────────
# PHASE 2: ARCHITECT – EVALUATE & ROUTE
# ──────────────────────────────────────────────
def run_architect_phase(architect_agent, job: dict) -> dict:
    """
    Run the Architect agent on a single job to score and route it.

    Args:
        architect_agent: The Architect DialogAgent instance.
        job: A dict with 'title', 'url', and 'company'.

    Returns:
        A dict with 'score', 'action', 'company', 'role', 'key_technologies',
        'jd_category', and 'reason'. Returns a SKIP result on errors.
    """
    url = job.get("url", "")
    logger.info(f"\n{'─' * 50}")
    logger.info(f"PHASE 2: THE ARCHITECT – Evaluating: {job.get('title', 'Unknown')}")
    logger.info(f"URL: {url}")

    # Step 1: Scrape the job page
    jd_text = scrape_job_page(url)

    if jd_text.startswith("ERROR"):
        logger.warning(f"[Architect] Scraping failed ({jd_text}). Falling back to basic title/company evaluation.")
        # Create a synthetic JD so the LLM can still draft an email
        jd_text = f"Job Title: {job.get('title', 'Unknown')}\nCompany: {job.get('company', extract_company_from_url(url))}\nDetails could not be scraped due to bot protection, but the search context implies an AI/ML or Data Science role suitable for a junior candidate."

    # Step 2: Tool-based scoring (fast, deterministic)
    tool_score = score_job(jd_text)

    # Step 3: Tool-based routing
    tool_action = route_action(url, tool_score)

    # Step 4: Ask the Architect LLM for deeper analysis
    architect_prompt = (
        f"Evaluate this job posting and return your analysis as JSON.\n\n"
        f"URL: {url}\n"
        f"Job Title (from search): {job.get('title', 'Unknown')}\n"
        f"Company (from search): {job.get('company', 'Unknown')}\n\n"
        f"JOB DESCRIPTION TEXT:\n{jd_text}\n\n"
        f"My tool-based pre-score is {tool_score} and pre-route is '{tool_action}'. "
        f"Confirm or override with your own analysis. Return the JSON."
    )

    architect_msg = Msg("user", architect_prompt, role="user")

    try:
        architect_response = architect_agent(architect_msg)
        llm_analysis = parse_json_from_response(architect_response.content)
    except Exception as e:
        logger.error(f"[Architect] LLM call failed: {e}")
        llm_analysis = None

    # Merge tool-based and LLM-based results
    if llm_analysis and isinstance(llm_analysis, dict):
        # LLM overrides, but we validate
        result = {
            "score": llm_analysis.get("score", tool_score),
            "action": llm_analysis.get("action", tool_action),
            "company": llm_analysis.get("company", job.get("company", "Unknown")),
            "role": llm_analysis.get("role", job.get("title", "Unknown")),
            "key_technologies": llm_analysis.get("key_technologies", []),
            "jd_category": llm_analysis.get("jd_category", "general"),
            "reason": llm_analysis.get("reason", "LLM analysis"),
            "jd_text": jd_text,
        }
        # Enforce: if score < 6, action MUST be SKIP
        if result["score"] < 6:
            result["action"] = "SKIP"
    else:
        # Fallback to pure tool-based results
        result = {
            "score": tool_score,
            "action": tool_action,
            "company": job.get("company", extract_company_from_url(url)),
            "role": job.get("title", "Unknown"),
            "key_technologies": [],
            "jd_category": "general",
            "reason": "Tool-based scoring (LLM unavailable)",
            "jd_text": jd_text,
        }

    logger.info(f"[Architect] Score: {result['score']}, Action: {result['action']}, "
                f"Category: {result['jd_category']}")
    return result


# ──────────────────────────────────────────────
# PHASE 3: GHOSTWRITER – DRAFT COLD EMAIL
# ──────────────────────────────────────────────
def run_ghostwriter_phase(ghostwriter_agent, analysis: dict) -> dict:
    """
    Run the Ghostwriter agent to draft a cold email for a job.

    Args:
        ghostwriter_agent: The Ghostwriter DialogAgent instance.
        analysis: The Architect's analysis dict.

    Returns:
        A dict with 'subject' and 'body' of the drafted email.
    """
    logger.info(f"PHASE 3: THE GHOSTWRITER – Drafting email for {analysis['company']}")

    email_context = {
        "company": analysis["company"],
        "role": analysis["role"],
        "key_technologies": analysis.get("key_technologies", []),
        "jd_category": analysis.get("jd_category", "general"),
        "reason": analysis.get("reason", ""),
        "recruiter_name": "",  # Will be filled if found
    }

    ghostwriter_prompt = (
        f"Draft a cold email for this job:\n\n"
        f"{json.dumps(email_context, indent=2)}\n\n"
        f"Remember: under 100 words, sound like a real person, and include the mandatory sign-off."
    )

    ghostwriter_msg = Msg("user", ghostwriter_prompt, role="user")

    try:
        response = ghostwriter_agent(ghostwriter_msg)
        email_text = response.content.strip()
    except Exception as e:
        logger.error(f"[Ghostwriter] LLM call failed: {e}")
        # Fallback email
        email_text = _fallback_email(analysis)

    # Parse subject and body
    subject = ""
    body = email_text

    if email_text.lower().startswith("subject:"):
        lines = email_text.split("\n", 1)
        subject = lines[0].replace("Subject:", "").replace("subject:", "").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
    else:
        subject = f"Application: {analysis['role']} at {analysis['company']} – Karan Bhoriya"

    # Ensure the mandatory sign-off is present
    signoff = KARAN_PROFILE["mandatory_signoff"]
    if "karanpr-18.github.io" not in body:
        body = body + "\n" + signoff

    logger.info(f"[Ghostwriter] Email drafted – Subject: {subject[:60]}...")
    return {"subject": subject, "body": body}


def _fallback_email(analysis: dict) -> str:
    """Generate a simple fallback email if the Ghostwriter LLM fails."""
    return f"""Subject: {analysis['role']} @ {analysis['company']} – Karan Bhoriya

Hi,

I'm Karan, a B.Tech AIML student. I saw the {analysis['role']} opening and had to reach out.

I've built 10+ AI projects, including a PyTorch LSTM model from scratch. Most notably, during my Humana internship, I built Python pipelines that cut QA time by 95% (4 days to 2 hours).

I'd love to bring that same focus on efficiency to {analysis['company']}. My links are below.

Best,
Karan Bhoriya

{KARAN_PROFILE['mandatory_signoff']}"""


# ──────────────────────────────────────────────
# PHASE 4: DISPATCHER – EXECUTE ACTIONS
# ──────────────────────────────────────────────
def run_dispatcher_phase(
    analysis: dict,
    email_draft: dict,
    job_url: str,
    dry_run: bool = False,
) -> dict:
    """
    Execute the final action (apply via Playwright or draft email) and log to tracker.

    Args:
        analysis: The Architect's analysis dict.
        email_draft: The Ghostwriter's email dict with 'subject' and 'body'.
        job_url: The original job URL.
        dry_run: If True, don't actually send emails or fill forms.

    Returns:
        A dict with the final execution result.
    """
    action = analysis["action"]
    company = analysis["company"]
    role = analysis["role"]
    today = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"PHASE 4: THE DISPATCHER – Executing '{action}' for {company}")

    result = {
        "company": company,
        "role": role,
        "url": job_url,
        "portal_status": "",
        "email_sent_to": "None",
        "application_status": "",
        "details": "",
    }

    # ── ACTION: SKIP ──
    if action == "SKIP":
        result["portal_status"] = f"Skipped (Low Fit Score: {analysis['score']})"
        result["application_status"] = "Skipped"
        result["details"] = analysis.get("reason", "Low score")
        logger.info(f"[Dispatcher] SKIP – {company} ({role})")

    # ── ACTION: PLAYWRIGHT_APPLY ──
    elif action == "PLAYWRIGHT_APPLY":
        if dry_run:
            result["portal_status"] = "DRY RUN – Would attempt Playwright"
            result["application_status"] = "Dry Run"
            logger.info(f"[Dispatcher] DRY RUN – Skipping Playwright for {company}")
        else:
            pw_result = playwright_apply(
                url=job_url,
                name=KARAN_PROFILE["name"],
                email=KARAN_PROFILE.get("email", ""),
                phone=KARAN_PROFILE.get("phone", ""),
                summary=f"B.Tech AIML student with 10+ projects in AI/ML. "
                        f"Built TalentAI (LLM recruitment platform), PyTorch models, "
                        f"and cut QA time by 95% at Humana.",
                resume_path=RESUME_PATH,
            )

            result["portal_status"] = pw_result["status"]
            result["details"] = pw_result["details"]

            if pw_result["success"]:
                result["application_status"] = "Applied"
                logger.info(f"[Dispatcher] ✅ Playwright apply succeeded for {company}")
            else:
                # Fallback to cold email
                logger.warning(f"[Dispatcher] Playwright failed, falling back to email for {company}")
                action = "SKIP_TO_EMAIL"  # Override to trigger email below

    # ── ACTION: SKIP_TO_EMAIL ──
    if action == "SKIP_TO_EMAIL":
        # Search for a hiring email
        hiring_email = search_hiring_email(company, job_url, analysis.get("jd_text", ""))

        if hiring_email and hiring_email != "None":
            if dry_run:
                result["portal_status"] = result.get("portal_status") or "Skipped (Portal)"
                result["email_sent_to"] = hiring_email
                result["application_status"] = "DRY RUN – Would draft email"
                logger.info(f"[Dispatcher] DRY RUN – Would email {hiring_email}")
            else:
                gmail_result = gmail_draft_email(
                    to_email=hiring_email,
                    subject=email_draft["subject"],
                    body=email_draft["body"],
                )

                result["email_sent_to"] = hiring_email

                if gmail_result["success"]:
                    result["portal_status"] = result.get("portal_status") or "Skipped (Portal)"
                    result["application_status"] = "Mailed"
                    result["details"] = f"Draft ID: {gmail_result['draft_id']}"
                    logger.info(f"[Dispatcher] ✅ Gmail draft created for {hiring_email}")
                else:
                    result["portal_status"] = result.get("portal_status") or "Skipped (Portal)"
                    result["application_status"] = f"Email Failed ({gmail_result['error'][:50]})"
                    logger.error(f"[Dispatcher] ❌ Gmail draft failed: {gmail_result['error']}")
        else:
            result["portal_status"] = result.get("portal_status") or "Skipped (Portal)"
            result["email_sent_to"] = "None"
            result["application_status"] = "Skipped (No email found)"
            logger.warning(f"[Dispatcher] No hiring email found for {company}")

    # ── ALWAYS: Append to tracker ──
    if not result["portal_status"]:
        result["portal_status"] = "Unknown"
    if not result["application_status"]:
        result["application_status"] = "Unknown"

    # ── ONLY Append to tracker if successful ──
    success_statuses = ["Mailed", "Applied", "Dry Run"]
    if result["application_status"] in success_statuses:
        append_to_tracker(
            date=today,
            company=result["company"],
            role=result["role"],
            url=result["url"],
            portal_status=result["portal_status"],
            email_sent_to=result["email_sent_to"],
            application_status=result["application_status"],
        )
    else:
        logger.info(f"[Dispatcher] Skipping CSV logging for unsuccessful/skipped job: {company}")

    return result


# ──────────────────────────────────────────────
# MAIN ORCHESTRATION PIPELINE
# ──────────────────────────────────────────────
def run_pipeline(force: bool = False, dry_run: bool = False):
    """
    Main orchestration pipeline that chains all four agents.

    Args:
        force: If True, ignore the 9am-5pm time restriction.
        dry_run: If True, don't execute actual applications or emails.
    """
    # ── Check work hours ──
    now = datetime.now()
    current_hour = now.hour

    if not force and not (WORK_HOURS_START <= current_hour < WORK_HOURS_END):
        logger.info(
            f"⏰ Outside work hours ({WORK_HOURS_START}:00 – {WORK_HOURS_END}:00). "
            f"Current time: {now.strftime('%H:%M')}. Use --force to override."
        )
        return

    logger.info("🚀 Starting AgentScope Multi-Agent Job Hunter Pipeline")
    logger.info(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"   Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Max applications: {MAX_APPLICATIONS_PER_DAY}")
    logger.info(f"   Delay between apps: {DELAY_BETWEEN_APPLICATIONS}s")

    # ── AgentScope initialization skipped (using LiteLLM directly) ──
    logger.info("✅ Initialized pipeline with Groq models via LiteLLM")

    # ── Create agents ──
    scout = create_scout_agent()
    architect = create_architect_agent()
    ghostwriter = create_ghostwriter_agent()
    # Dispatcher is tool-driven, not a separate LLM agent in execution
    logger.info("✅ All agents created")
    write_status(step="Starting Pipeline", done=0)

    # ── Load existing tracker URLs ──
    existing_urls = load_existing_urls()
    logger.info(f"📊 Tracker has {len(existing_urls)} existing URLs")

    # ── PHASE 1: SCOUT ──
    jobs = run_scout_phase(scout, existing_urls)

    if not jobs:
        logger.info("🏁 No new jobs found. Pipeline complete.")
        return

    # Cap to daily limit
    jobs = jobs[:MAX_APPLICATIONS_PER_DAY]
    logger.info(f"\n📋 Processing {len(jobs)} jobs through the pipeline\n")

    # ── PROCESS EACH JOB ──
    processed_count = 0
    results_summary = []

    for i, job in enumerate(jobs):
        url = job.get("url", "")

        if not url or url in existing_urls:
            logger.info(f"[{i+1}/{len(jobs)}] Skipping (no URL or already tracked)")
            continue

        logger.info(f"\n{'═' * 60}")
        logger.info(f"[{i+1}/{len(jobs)}] Processing: {job.get('title', 'Unknown')}")
        logger.info(f"{'═' * 60}")

        try:
            # PHASE 2: ARCHITECT – Evaluate & Route
            analysis = run_architect_phase(architect, job)

            # PHASE 3: GHOSTWRITER – Draft email (only if needed)
            email_draft = {"subject": "", "body": ""}
            if analysis["action"] in ("SKIP_TO_EMAIL", "PLAYWRIGHT_APPLY"):
                email_draft = run_ghostwriter_phase(ghostwriter, analysis)

            # PHASE 4: DISPATCHER – Execute
            result = run_dispatcher_phase(analysis, email_draft, url, dry_run)
            results_summary.append(result)

            # Add to existing URLs to prevent re-processing
            existing_urls.add(url)
            
            # Update progress for every job in the list
            current_progress = i + 1
            status_step = f"Phase: {analysis.get('action', 'Skip')}"
            write_status(step=status_step, done=current_progress, total=len(jobs))

        except Exception as e:
            logger.error(f"❌ Error processing job {url}: {e}", exc_info=True)
            # Log the failure to tracker
            append_to_tracker(
                date=datetime.now().strftime("%Y-%m-%d"),
                company=job.get("company", extract_company_from_url(url)),
                role=job.get("title", "Unknown"),
                url=url,
                portal_status="Error",
                email_sent_to="None",
                application_status=f"Pipeline Error: {str(e)[:80]}",
            )
            continue

        # ── Rate limiting: ONLY if mail was sent or application succeeded ──
        if i < len(jobs) - 1:
            success_statuses = ["Mailed", "Applied", "Dry Run"]
            is_success = results_summary and results_summary[-1].get("application_status") in success_statuses
            
            if is_success and DELAY_BETWEEN_APPLICATIONS > 0:
                logger.info(f"\n⏳ Cooling off for {DELAY_BETWEEN_APPLICATIONS // 60} minutes "
                            f"before next application...")
                
                # Check if we're still within work hours
                check_time = datetime.now()
                if not force and check_time.hour >= WORK_HOURS_END:
                    logger.info("⏰ Work hours ended. Stopping pipeline.")
                    break

                time.sleep(DELAY_BETWEEN_APPLICATIONS)
            else:
                logger.info("[Pipeline] Moving directly to next lead.")

    # ── SUMMARY ──
    logger.info(f"\n{'═' * 60}")
    logger.info("🏁 PIPELINE COMPLETE – SUMMARY")
    logger.info(f"{'═' * 60}")
    logger.info(f"Total jobs discovered: {len(jobs)}")
    logger.info(f"Total jobs processed: {processed_count}")

    # Breakdown by status
    statuses = {}
    for r in results_summary:
        status = r.get("application_status", "Unknown")
        statuses[status] = statuses.get(status, 0) + 1

    for status, count in sorted(statuses.items()):
        logger.info(f"  {status}: {count}")

    logger.info(f"\n📁 Tracker updated: {TRACKER_CSV_PATH}")
    logger.info(f"📁 Logs saved to: {LOG_DIR}")
    write_status(status="finished", step="All Done", done=processed_count, total=processed_count)


# ──────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AgentScope Multi-Agent Job Hunter – Automated AI/ML internship applications"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force run regardless of work hours (9am-5pm restriction)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run – discover and evaluate jobs but don't actually apply or email",
    )

    args = parser.parse_args()

    try:
        run_pipeline(force=args.force, dry_run=args.dry_run)
    except KeyboardInterrupt:
        logger.info("\n🛑 Pipeline interrupted by user.")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)
