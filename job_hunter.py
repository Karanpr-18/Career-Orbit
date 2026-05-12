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
)
from tools import (
    serper_search,
    scrape_job_page,
    score_job,
    route_action,
    playwright_apply,
    gmail_draft_email,
    append_to_tracker,
    load_existing_urls,
    count_successful_sends,
    verify_email_with_emailable,
    extract_company_from_url,
    search_hiring_email,
    extract_cv_text,
)

# ──────────────────────────────────────────────
# STATUS REPORTING SETUP
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_PATH = os.path.join(BASE_DIR, "agent_status.json")


def write_status(status="running", step="Initializing", done=0, total=50):
    try:
        # Preserve PID from existing file if possible
        pid = None
        if os.path.exists(STATUS_PATH):
            try:
                with open(STATUS_PATH, "r") as rf:
                    old_data = json.load(rf)
                    pid = old_data.get("pid")
            except:
                pass

        with open(STATUS_PATH, "w") as f:
            json.dump({
                "status": status,
                "step": step,
                "progress": {"done": done, "total": total},
                "last_update": datetime.now().strftime("%H:%M:%S"),
                "pid": pid
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

    Uses Serper.dev Google Search (API-based) and then asks the Scout LLM
    to evaluate and filter the raw results.

    Args:
        scout_agent: The Scout DialogAgent instance.
        existing_urls: Set of URLs already in the tracker.

    Returns:
        A list of dicts with 'title', 'url', and 'company' for new jobs.
    """
    logger.info("PHASE 1: THE SCOUT – Discovering new job postings")
    logger.info("=" * 60)
    write_status(step="Scouting", done=count_successful_sends(), total=50)

    all_raw_results = []

    def _parse_serper_results(text: str) -> list[dict]:
        parsed = []
        if "Search Error" in text: return parsed
        blocks = text.split("Result ")
        for block in blocks:
            if not block.strip(): continue
            title = re.search(r"Title:\s*(.*)", block)
            link = re.search(r"Link:\s*(.*)", block)
            snippet = re.search(r"Snippet:\s*(.*)", block)
            if title and link:
                parsed.append({
                    "title": title.group(1).strip(),
                    "url": link.group(1).strip(),
                    "snippet": snippet.group(1).strip() if snippet else ""
                })
        return parsed

    # Step 1: Run web searches for each query + site combination
    total_queries = len(SEARCH_QUERIES)
    for i, query in enumerate(SEARCH_QUERIES):
        logger.info(f"🔍 Searching [{i+1}/{total_queries}]: {query}...")
        write_status(step=f"Scouting: {query}", done=count_successful_sends(), total=50)
        
        # Search across all sites
        results_str = serper_search(query)
        all_raw_results.extend(_parse_serper_results(results_str))

        # Search top 3 most productive sites specifically to save time/API quota
        for site in TARGET_SITES[:3]: 
            site_query = f'site:{site} "{query}"'
            results_str = serper_search(site_query)
            all_raw_results.extend(_parse_serper_results(results_str))

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
    
    for i in range(0, min(len(unique_results), 300), chunk_size):
        chunk = unique_results[i:i+chunk_size]
        search_summary = json.dumps(chunk, indent=1)
        
        scout_prompt = (
            "Filter these job postings to ONLY keep AI/ML/Data Science roles suitable for a student or junior (Internships, Junior, Associate).\n"
            "STRICT FILTERS:\n"
            "1. LOCATION: If the job is outside India, it MUST be explicitly 'Remote'. Discard international roles that require relocation.\n"
            "2. NATIONALITY: Exclude jobs that mention specific citizenship requirements (e.g., 'US Citizen only', 'EU residents only').\n"
            "3. SENIORITY: Exclude Senior/Lead roles with 3+ years experience.\n\n"
            "Return a JSON array with 'title', 'url', and 'company'.\n\n"
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
def run_architect_phase(architect_agent, job: dict, my_cv_text: str) -> dict:
    """
    Run the Architect agent on a single job to score and route it.
    """
    write_status(step="Reviewing", done=count_successful_sends(), total=50)
    url = job.get("url", "")
    logger.info(f"\n{'─' * 50}")
    logger.info(f"PHASE 2: THE ARCHITECT – Evaluating: {job.get('title', 'Unknown')}")
    logger.info(f"URL: {url}")

    # Step 1: Scrape the job page
    jd_text = scrape_job_page(url)

    if jd_text.startswith("ERROR"):
        logger.warning(f"[Architect] Scraping failed. Using search metadata for evaluation.")
        jd_text = f"Job Title: {job.get('title', 'Unknown')}\nCompany: {job.get('company', 'Unknown')}\n[Full JD could not be scraped]"

    # Step 2: Tool-based scoring (for fallback/signal)
    tool_score = score_job(jd_text)
    tool_action = route_action(url, tool_score)

    # Step 3: Dynamic CV-JD Matching Prompt
    architect_prompt = (
        "You are an expert tech recruiter. I will give you a Job Description and my current CV.\n"
        "Evaluate how well my CV matches this job.\n\n"
        f"MY CV:\n{my_cv_text}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        "Score the match from 1-10 based ONLY on the skills and experience present in my CV compared to their requirements. "
        "Output a JSON containing 'score' and 'reason'."
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
def run_ghostwriter_phase(ghostwriter_agent, analysis: dict, my_cv_text: str) -> dict:
    """
    Run the Ghostwriter agent to draft a highly personalized cold email.
    """
    write_status(step="Drafting", done=count_successful_sends(), total=50)
    logger.info(f"PHASE 3: THE GHOSTWRITER – Drafting personalized email for {analysis['company']}")

    jd_text = analysis.get("jd_text", "See job title and company.")
    job_title = analysis.get("role", "Job Title")
    company_name = analysis.get("company", "Company")

    ghostwriter_prompt = (
        "You are an elite executive assistant writing a cold email to a hiring manager.\n"
        f"Write a short, highly personalized cold email applying for the {job_title} role at {company_name}.\n\n"
        f"MY CV:\n{my_cv_text}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        "Email Structure Rules:\n\n"
        f"Subject Line: Keep it under 6 words, professional and intriguing (e.g., 'Experienced AI Engineer for {company_name}').\n\n"
        "Paragraph 1 (The Hook): 1-2 sentences. State the role you are applying for and mention one specific, impressive thing about their company from the JD to show you did your research.\n\n"
        "Paragraph 2 (The Value Pitch): 2 sentences max. Extract exactly ONE major achievement or skill from MY CV that directly solves a problem mentioned in THEIR JOB DESCRIPTION. Do not list all my skills. Be hyper-specific (e.g., 'I saw you need help with X. At my previous role, I built Y using [Skill from CV]').\n\n"
        "Paragraph 3 (The CTA): 1 sentence. A soft call to action asking for a brief chat, followed by a professional sign-off with my name.\n\n"
        "Tone: Confident, concise, and human. No corporate jargon, no fluff, no 'I hope this email finds you well'.\n\n"
        "Evidence-Based Writer Constraint: You are strictly forbidden from mentioning any skill or experience not found in MY_CV_TEXT. Do not assume or fill in gaps. If a skill is not explicitly in the CV, do not mention it.\n\n"
        "Output ONLY the email text (Subject and Body)."
        "Keep mail under 100 words"
    )

    ghostwriter_msg = Msg("user", ghostwriter_prompt, role="user")

    try:
        response = ghostwriter_agent(ghostwriter_msg)
        email_text = response.content.strip()
    except Exception as e:
        logger.error(f"[Ghostwriter] LLM call failed: {e}")
        # Fallback email
        email_text = _fallback_email(analysis)

    # Clean markdown
    clean_text = email_text.replace("**", "").strip()
    
    import re
    match = re.match(r"(?i)^(?:subject:\s*)(.*?)(?:\n\s*(?:body:)?\s*\n|\n)(.*)", clean_text, re.DOTALL)
    if match:
        subject = match.group(1).strip()
        body = match.group(2).strip()
    else:
        subject = f"Application: {analysis.get('role', 'Unknown')} at {analysis.get('company', 'Unknown')} – Karan Bhoriya"
        body = clean_text
        
    body = re.sub(r"(?i)^body:\s*", "", body).strip()

    # Ensure the mandatory sign-off is present
    signoff = KARAN_PROFILE["mandatory_signoff"]
    if "karanpr-18.github.io" not in body:
        body = body + "\n" + signoff

    logger.info(f"[Ghostwriter] Email drafted – Subject: {subject[:60]}...")
    return {"subject": subject, "body": body}
def run_compliance_check(architect_agent, email_draft: str, my_cv_text: str) -> str:
    """
    Architect performs a compliance check to ensure zero hallucination.
    """
    logger.info("[Architect] Running Hallucination Compliance Check...")
    
    compliance_prompt = (
        "You are a strict compliance officer. Compare this Email Draft to my CV.\n"
        "If the email mentions ANY skill, project, or experience NOT found in my CV, delete those specific sentences.\n"
        "Do not change the rest of the email. Return only the cleaned email text.\n\n"
        f"MY CV:\n{my_cv_text}\n\n"
        f"EMAIL DRAFT:\n{email_draft}"
    )
    
    msg = Msg("user", compliance_prompt, role="user")
    try:
        response = architect_agent(msg)
        return response.content.strip()
    except Exception as e:
        logger.warning(f"[Architect] Compliance check failed: {e}")
        return email_draft


def _fallback_email(analysis: dict) -> str:
    """Generate a simple fallback email if the Ghostwriter LLM fails."""
    return f"""Subject: {analysis['role']} @ {analysis['company']} – Karan Bhoriya
 
 Hi,
 
 I'm Karan, a B.Tech AIML student specializing in Agentic AI and GenAI. I saw the {analysis['role']} opening and had to reach out.
 
 I've built end-to-end LLM platforms like TalentAI and autonomous agents like Career-Orbit. During my Humana internship, I also engineered Python pipelines that cut QA time by 95% (4 days to 2 hours).
 
 I'd love to bring that same focus on GenAI efficiency to {analysis['company']}. My links are below.

Best,
Karan Bhoriya

{KARAN_PROFILE['mandatory_signoff']}"""


# ──────────────────────────────────────────────
# PHASE 4: DISPATCHER – EXECUTE ACTIONS
# ──────────────────────────────────────────────
def run_dispatcher_phase(
    analysis: dict,
    job_url: str,
    ghostwriter=None,
    architect=None,
    dry_run: bool = False,
    my_cv_text: str = "",
) -> bool:
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
    write_status(step="Mailing", done=count_successful_sends(), total=50)

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
                my_cv_text=my_cv_text,
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
        # ── ONLY Trigger Investigator (Search) if Match Score is High (8+) ──
        if analysis.get("score", 0) >= 8:
            logger.info(f"[Dispatcher] High score ({analysis['score']}). Triggering Investigator for hiring email...")
            hiring_email = search_hiring_email(company, job_url, analysis.get("jd_text", ""))
        else:
            logger.info(f"[Dispatcher] Score {analysis.get('score')} is moderate/low. Skipping Investigator to save credits.")
            hiring_email = "None"

        if hiring_email and "@" in hiring_email:
            # ── EMAILABLE VERIFICATION ──
            verification = verify_email_with_emailable(hiring_email)
            if not verification["success"]:
                logger.warning(f"[Dispatcher] ❌ Email {hiring_email} failed verification ({verification['state']}, Score: {verification['score']}). Skipping to avoid bounce.")
                result["application_status"] = f"Skipped (Invalid Email: {verification['state']})"
                return False
                
            if dry_run:
                result["portal_status"] = result.get("portal_status") or "Skipped (Portal)"
                result["email_sent_to"] = hiring_email
                result["application_status"] = "DRY RUN – Would draft email"
                logger.info(f"[Dispatcher] DRY RUN – Would email {hiring_email}")
            else:
                # TOKEN SAVING: Draft only AFTER verification
                logger.info("[Dispatcher] Email verified. Drafting personalized message...")
                email_draft_raw = run_ghostwriter_phase(ghostwriter, analysis, my_cv_text)
                clean_body = run_compliance_check(architect, email_draft_raw["body"], my_cv_text)
                email_draft = {"subject": email_draft_raw["subject"], "body": clean_body}
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
    is_success = result["application_status"] in success_statuses

    if is_success:
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

    return is_success


def process_job(job, scout, architect, ghostwriter, dry_run, my_cv_text):
    """
    Orchestrates the lifecycle of a single job.
    """
    # Phase 2: Architect (Score & Route)
    analysis = run_architect_phase(architect, job, my_cv_text)
    
    # Phase 4: Dispatcher (Execute & Log)
    # The dispatcher handles Phase 3 (Ghostwriter) internally for token savings.
    is_sent = run_dispatcher_phase(
        analysis=analysis,
        job_url=job["url"],
        ghostwriter=ghostwriter,
        architect=architect,
        dry_run=dry_run,
        my_cv_text=my_cv_text
    )
    
    return is_sent


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
    
    # ── Load actual CV text for dynamic scoring & drafting ──
    MY_CV_TEXT = extract_cv_text(RESUME_PATH)
    logger.info(f"📄 Loaded CV text ({len(MY_CV_TEXT)} chars) for dynamic personalization")

    now = datetime.now()
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
    
    logger.info(f"🔍 Architect Model: {architect.model}")
    logger.info(f"✍️ Ghostwriter Model: {ghostwriter.model}")
    
    # Dispatcher is tool-driven, not a separate LLM agent in execution
    logger.info("✅ All agents created")
    write_status(step="Starting Pipeline", done=0)

    # ── Load existing tracker URLs ──
    existing_urls = load_existing_urls()
    logger.info(f"📊 Tracker has {len(existing_urls)} existing URLs")

    # ── Success-Targeted Hunting Strategy ──
    successful_sends = count_successful_sends()
    target_apps = 50
    total_checked = 0
    
    logger.info(f"📊 Resuming pipeline. Previous successful sends: {successful_sends}/{target_apps}")

    while successful_sends < target_apps:
        # Step 1: Scout for a batch of jobs
        jobs = run_scout_phase(scout, existing_urls)
        
        if not jobs:
            logger.info("🕵️ Job queue empty. Autonomously hunting for more leads...")
            # Autonomous Search: Remote Python Developer Jobs India
            autonomous_query = "Remote Python Developer Jobs India"
            res_str = serper_search(autonomous_query)
            
            def _parse(text: str) -> list[dict]:
                parsed = []
                if "Search Error" in text: return parsed
                blocks = text.split("Result ")
                for block in blocks:
                    if not block.strip(): continue
                    title = re.search(r"Title:\s*(.*)", block)
                    link = re.search(r"Link:\s*(.*)", block)
                    if title and link:
                        parsed.append({"title": title.group(1).strip(), "url": link.group(1).strip()})
                return parsed
                
            jobs = _parse(res_str)
            if not jobs:
                logger.info("🏁 No more new jobs found even after autonomous search. Ending.")
                break

        logger.info(f"\n📋 Processing batch of {len(jobs)} jobs. Current progress: {successful_sends}/{target_apps}\n")

        for job in jobs:
            if successful_sends >= target_apps: break

            total_checked += 1
            url = job.get("url", "")
            if not url or url in existing_urls: continue

            logger.info(f"\n{'═' * 60}")
            logger.info(f"HUNTING [{successful_sends+1}/{target_apps}] | Checked: {total_checked} | Processing: {job.get('title', 'Unknown')}")
            logger.info(f"{'═' * 60}")
            try:
                is_sent = process_job(
                    job=job,
                    scout=scout,
                    architect=architect,
                    ghostwriter=ghostwriter,
                    dry_run=dry_run,
                    my_cv_text=MY_CV_TEXT
                )
                
                if is_sent:
                    successful_sends += 1
                    logger.info(f"✨ SUCCESS! Progress: {successful_sends}/{target_apps}")
                
                # Update status for the dashboard with progress bar
                write_status(
                    step=f"Mailing: Progress {successful_sends}/{target_apps}",
                    done=successful_sends,
                    total=target_apps
                )

                existing_urls.add(url)

            except Exception as e:
                logger.error(f"❌ Error processing job {url}: {e}", exc_info=True)
                continue

            # ── Rate limiting and Safety ──
            if is_sent and successful_sends < target_apps and DELAY_BETWEEN_APPLICATIONS > 0:
                logger.info(f"⏳ Cooling off for {DELAY_BETWEEN_APPLICATIONS}s...")
                time.sleep(DELAY_BETWEEN_APPLICATIONS)

    # ── FINAL SUMMARY ──
    logger.info(f"\n{'═' * 60}")
    logger.info("🏁 HUNTING SESSION COMPLETE")
    logger.info(f"{'═' * 60}")
    logger.info(f"Target: {target_apps} | Successfully Sent: {successful_sends} | Total Checked: {total_checked}")
    write_status(status="finished", step="Hunting Session Complete", done=successful_sends, total=target_apps)


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
