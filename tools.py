"""
tools.py – Custom tool functions for the AgentScope Multi-Agent Job Hunter.

Provides:
  1. web_search_jobs    – DuckDuckGo search for job postings
  2. scrape_job_page    – BeautifulSoup scraper to extract JD text
  3. score_job          – Keyword-based scoring of a JD
  4. route_action       – Determines PLAYWRIGHT_APPLY, SKIP_TO_EMAIL, or SKIP
  5. playwright_apply   – Fills application forms via Playwright
  6. gmail_draft_email  – Creates a Gmail draft via the Gmail API
  7. append_to_tracker  – Appends a row to tracker.csv
  8. load_existing_urls – Reads tracker.csv to get already-processed URLs
"""

import csv
import os
import re
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

import requests
import re
from crawl4ai import WebCrawler
from agents import LiteLLMAgent
from agentscope.message import Msg

logger = logging.getLogger("job_hunter.tools")

# ──────────────────────────────────────────────
# 1. WEB SEARCH (DuckDuckGo)
# ──────────────────────────────────────────────
def searxng_search(query: str) -> str:
    """
    Search the web for job postings using SearxNG.
    Returns title and URL for the top 3 results.
    """
    try:
        url = "https://searx.be/search"
        params = {"q": query, "format": "json"}
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        results = data.get("results", [])[:3]
        
        output = ""
        for r in results:
            output += f"Title: {r.get('title')}\nURL: {r.get('url')}\n\n"
        
        return output.strip()
    except Exception as e:
        logger.error(f"[Scout] SearxNG search failed: {e}")
        return f"Error: {e}"


def crawl_page(url: str) -> str:
    """
    Crawl a page using Crawl4AI to bypass bot protection.
    Returns the first 2500 characters of markdown.
    """
    try:
        crawler = WebCrawler()
        crawler.warmup()
        result = crawler.run(url=url, bypass_cache=True)
        # Return first 2500 chars to stay within TPM limits
        return result.markdown[:2500]
    except Exception as e:
        logger.error(f"[Architect] Crawl4AI failed for {url}: {e}")
        return f"Error: {e}"


# ──────────────────────────────────────────────
# 2. SCRAPE JOB PAGE
# ──────────────────────────────────────────────
def scrape_job_page(url: str) -> str:
    """
    Scrape the text content of a job posting page.

    Args:
        url: The URL of the job posting.

    Returns:
        The extracted text content of the page (truncated to ~4000 chars for LLM context).
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script, style, nav, footer elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        # Truncate to prevent blowing up the LLM context
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000] + "\n... [truncated]"

        logger.info(f"[Architect] Scraped {len(clean_text)} chars from {url[:60]}")
        return clean_text

    except Exception as e:
        logger.warning(f"[Architect] Requests failed for {url}: {e}. Trying Playwright fallback...")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                text = page.inner_text("body")
                browser.close()
                
                # Clean up excessive whitespace
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                clean_text = "\n".join(lines)
                if len(clean_text) > 4000:
                    clean_text = clean_text[:4000] + "\n... [truncated]"
                
                logger.info(f"[Architect] Playwright fallback successful for {url[:60]}")
                return clean_text
        except Exception as pe:
            logger.error(f"[Architect] Playwright fallback also failed for {url}: {pe}")
            return f"ERROR: Could not scrape page – {e}"


# ──────────────────────────────────────────────
# 3. SCORE JOB DESCRIPTION
# ──────────────────────────────────────────────
def score_job(jd_text: str) -> int:
    """
    Score a job description based on keyword matching.

    Scoring rules:
      - Score 10: Mentions LLMs, PyTorch, Model Optimization, etc.
      - Score 8:  Mentions Scikit-learn, SQL, Python-heavy DS, etc.
      - Score <7: Generic Data Analyst or Excel-heavy roles.

    Args:
        jd_text: The raw job description text.

    Returns:
        An integer score (10, 8, or 5).
    """
    from config import SCORE_10_KEYWORDS, SCORE_8_KEYWORDS, SCORE_SKIP_KEYWORDS

    jd_lower = jd_text.lower()

    # Check for skip keywords first
    skip_count = sum(1 for kw in SCORE_SKIP_KEYWORDS if kw in jd_lower)
    high_count = sum(1 for kw in SCORE_10_KEYWORDS if kw in jd_lower)
    mid_count = sum(1 for kw in SCORE_8_KEYWORDS if kw in jd_lower)

    # If mostly skip keywords and barely any high-value ones, mark as low
    if skip_count >= 2 and high_count == 0:
        logger.info(f"[Architect] Score: 5 (skip keywords dominant)")
        return 5

    if high_count >= 2:
        logger.info(f"[Architect] Score: 10 (high-value keywords: {high_count})")
        return 10

    if mid_count >= 2:
        logger.info(f"[Architect] Score: 8 (mid-value keywords: {mid_count})")
        return 8

    # Default to mid if there's some signal but not enough
    if high_count >= 1 or mid_count >= 1:
        logger.info(f"[Architect] Score: 8 (some signal found)")
        return 8

    logger.info(f"[Architect] Score: 5 (no strong keywords)")
    return 5


# ──────────────────────────────────────────────
# 4. ROUTE ACTION
# ──────────────────────────────────────────────
def route_action(url: str, score: int) -> str:
    """
    Determine the action to take based on URL domain and score.

    Returns one of:
      - "PLAYWRIGHT_APPLY" – attempt form fill via browser
      - "SKIP_TO_EMAIL"    – skip form, draft cold email
      - "SKIP"             – low score, do nothing

    Args:
        url: The job posting URL.
        score: The job's fit score.

    Returns:
        Action string.
    """
    from config import LOGIN_REQUIRED_DOMAINS, PLAYWRIGHT_APPLY_DOMAINS

    if score < 7:
        logger.info(f"[Architect] SKIP – score {score} too low for {url[:50]}")
        return "SKIP"

    parsed = urlparse(url).netloc.lower()

    # Check if login is required
    for domain in LOGIN_REQUIRED_DOMAINS:
        if domain in parsed:
            logger.info(f"[Architect] SKIP_TO_EMAIL – login required at {parsed}")
            return "SKIP_TO_EMAIL"

    # Check if it's a Playwright-eligible portal
    for domain in PLAYWRIGHT_APPLY_DOMAINS:
        if domain in parsed or domain in url.lower():
            logger.info(f"[Architect] PLAYWRIGHT_APPLY – form fill possible at {parsed}")
            return "PLAYWRIGHT_APPLY"

    # Default: try email for unknown portals (safer than crashing on random forms)
    logger.info(f"[Architect] SKIP_TO_EMAIL – unknown portal {parsed}, defaulting to email")
    return "SKIP_TO_EMAIL"


# ──────────────────────────────────────────────
# 5. PLAYWRIGHT FORM FILL
# ──────────────────────────────────────────────
def playwright_apply(
    url: str,
    name: str = "Karan Bhoriya",
    email: str = "",
    phone: str = "",
    summary: str = "",
    resume_path: str = "",
) -> dict:
    """
    Attempt to fill out a job application form using Playwright.

    If a login wall is detected or the form fails, returns a failure status
    so the orchestrator can fall back to cold email.

    Args:
        url: The job application URL.
        name: Applicant's full name.
        email: Applicant's email address.
        phone: Applicant's phone number.
        summary: A short professional summary.
        resume_path: Absolute path to the resume PDF to upload.

    Returns:
        A dict with 'success' (bool), 'status' (str), and 'details' (str).
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # headful for debugging
            context = browser.new_context()
            page = context.new_page()

            logger.info(f"[Dispatcher] Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)  # Let JS render

            page_text = page.inner_text("body").lower()

            # ── Login detection ──
            login_indicators = [
                "sign in", "log in", "login", "create account",
                "sign up", "authentication required",
            ]
            if any(indicator in page_text for indicator in login_indicators):
                # Check if it's actually a login *wall* vs just a nav link
                # Look for prominent login forms
                login_forms = page.query_selector_all(
                    "form[action*='login'], form[action*='signin'], "
                    "input[type='password']"
                )
                if login_forms:
                    browser.close()
                    logger.warning(f"[Dispatcher] Login wall detected at {url}")
                    return {
                        "success": False,
                        "status": "Skipped (Login Required)",
                        "details": "Login wall detected, falling back to email.",
                    }

            # ── Try to fill common form fields ──
            filled_fields = []

            # Name fields
            for selector in [
                'input[name*="name" i]',
                'input[placeholder*="name" i]',
                'input[id*="name" i]',
                'input[aria-label*="name" i]',
            ]:
                elements = page.query_selector_all(selector)
                for el in elements:
                    el_type = el.get_attribute("type") or "text"
                    if el_type in ("text", ""):
                        try:
                            el.fill(name)
                            filled_fields.append("name")
                            break
                        except Exception:
                            continue
                if "name" in filled_fields:
                    break

            # Email fields
            for selector in [
                'input[type="email"]',
                'input[name*="email" i]',
                'input[placeholder*="email" i]',
            ]:
                elements = page.query_selector_all(selector)
                for el in elements:
                    try:
                        el.fill(email)
                        filled_fields.append("email")
                        break
                    except Exception:
                        continue
                if "email" in filled_fields:
                    break

            # Phone fields
            if phone:
                for selector in [
                    'input[type="tel"]',
                    'input[name*="phone" i]',
                    'input[placeholder*="phone" i]',
                ]:
                    elements = page.query_selector_all(selector)
                    for el in elements:
                        try:
                            el.fill(phone)
                            filled_fields.append("phone")
                            break
                        except Exception:
                            continue
                    if "phone" in filled_fields:
                        break

            # Resume upload
            if resume_path and os.path.exists(resume_path):
                for selector in [
                    'input[type="file"]',
                    'input[name*="resume" i]',
                    'input[accept*="pdf" i]',
                ]:
                    elements = page.query_selector_all(selector)
                    for el in elements:
                        try:
                            el.set_input_files(resume_path)
                            filled_fields.append("resume")
                            break
                        except Exception:
                            continue
                    if "resume" in filled_fields:
                        break

            # Summary / cover letter / additional info textarea
            if summary:
                for selector in [
                    'textarea[name*="summary" i]',
                    'textarea[name*="cover" i]',
                    'textarea[name*="additional" i]',
                    'textarea[placeholder*="tell us" i]',
                    "textarea",
                ]:
                    elements = page.query_selector_all(selector)
                    for el in elements:
                        try:
                            el.fill(summary)
                            filled_fields.append("summary")
                            break
                        except Exception:
                            continue
                    if "summary" in filled_fields:
                        break

            # ── Manual Review Pause (instead of screenshot) ──
            logger.info(f"[Dispatcher] Form filled. Browser will stay open for 60 seconds for you to click Submit.")
            time.sleep(60)

            browser.close()

            if filled_fields:
                status = f"Applied (Fields: {', '.join(filled_fields)})"
                logger.info(f"[Dispatcher] Form partially filled: {filled_fields}")
                return {
                    "success": True,
                    "status": status,
                    "details": f"Filled fields: {filled_fields}. Screenshot: {screenshot_path}",
                }
            else:
                logger.warning(f"[Dispatcher] No fields found to fill at {url}")
                return {
                    "success": False,
                    "status": "Skipped (No form fields found)",
                    "details": "Could not locate any standard form fields.",
                }

    except Exception as e:
        logger.error(f"[Dispatcher] Playwright failed for {url}: {e}")
        return {
            "success": False,
            "status": f"Skipped (Playwright Error)",
            "details": str(e),
        }


# ──────────────────────────────────────────────
# 6. GMAIL DRAFT EMAIL
# ──────────────────────────────────────────────
def gmail_draft_email(
    to_email: str,
    subject: str,
    body: str,
    credentials_path: str = "",
    token_path: str = "",
) -> dict:
    """
    Create a Gmail draft using the Gmail API with OAuth2.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        credentials_path: Path to Google OAuth2 credentials.json.
        token_path: Path to store/retrieve the OAuth token.

    Returns:
        A dict with 'success' (bool), 'draft_id' (str or None), and 'error' (str or None).
    """
    from config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH

    if not credentials_path:
        credentials_path = GMAIL_CREDENTIALS_PATH
    if not token_path:
        token_path = GMAIL_TOKEN_PATH

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        import base64
        from email.mime.text import MIMEText

        SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
        creds = None

        # Load existing token
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    return {
                        "success": False,
                        "draft_id": None,
                        "error": f"Gmail credentials not found at {credentials_path}. "
                                 "Download from Google Cloud Console.",
                    }
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for next run
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)

        # Create the email message
        message = MIMEText(body)
        message["to"] = to_email
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Create draft
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )

        logger.info(f"[Dispatcher] Gmail draft created for {to_email}: {draft['id']}")
        return {
            "success": True,
            "draft_id": draft["id"],
            "error": None,
        }

    except Exception as e:
        logger.error(f"[Dispatcher] Gmail draft failed for {to_email}: {e}")
        return {
            "success": False,
            "draft_id": None,
            "error": str(e),
        }


# ──────────────────────────────────────────────
# 7. TRACKER CSV OPERATIONS
# ──────────────────────────────────────────────
def load_existing_urls(tracker_path: str = "") -> set:
    """
    Load all URLs already present in the tracker CSV.

    Args:
        tracker_path: Path to the tracker CSV file.

    Returns:
        A set of URL strings already in the tracker.
    """
    from config import TRACKER_CSV_PATH

    if not tracker_path:
        tracker_path = TRACKER_CSV_PATH

    urls = set()
    if not os.path.exists(tracker_path):
        return urls

    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Extract URLs using a simple regex
            url_pattern = re.compile(r"https?://[^\s,'\"\r\n]+")
            urls = set(url_pattern.findall(content))

        logger.info(f"[Tracker] Loaded {len(urls)} existing URLs from tracker.")
        return urls

    except Exception as e:
        logger.error(f"[Tracker] Failed to load URLs: {e}")
        return urls


def append_to_tracker(
    date: str,
    company: str,
    role: str,
    url: str,
    portal_status: str,
    email_sent_to: str,
    application_status: str,
    tracker_path: str = "",
) -> bool:
    """
    Append a new row to the tracker CSV.

    Args:
        date: Date string (YYYY-MM-DD).
        company: Company name.
        role: Job role title.
        url: Job posting URL.
        portal_status: Status of portal application attempt.
        email_sent_to: Email address cold mail was sent to, or 'None'.
        application_status: Overall application status.
        tracker_path: Path to the tracker CSV file.

    Returns:
        True if the row was successfully appended, False otherwise.
    """
    from config import TRACKER_CSV_PATH

    if not tracker_path:
        tracker_path = TRACKER_CSV_PATH

    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(tracker_path), exist_ok=True)

        with open(tracker_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow([
                date, company, role, url,
                portal_status, email_sent_to, application_status,
            ])

        logger.info(f"[Tracker] Appended: {company} – {role}")
        return True

    except Exception as e:
        logger.error(f"[Tracker] Failed to append row: {e}")
        return False


# ──────────────────────────────────────────────
# 8. UTILITY: EXTRACT COMPANY NAME FROM URL
# ──────────────────────────────────────────────
def extract_company_from_url(url: str) -> str:
    """
    Attempt to extract a company name from a job URL.

    Args:
        url: The job posting URL.

    Returns:
        A best-guess company name string.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Strip common prefixes
    for prefix in ["www.", "jobs.", "careers.", "boards.", "job-boards.", "apply."]:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]

    # For job boards, try to extract from the path
    job_board_domains = [
        "greenhouse.io", "lever.co", "workable.com",
        "wellfound.com", "linkedin.com", "naukri.com",
        "instahyre.com",
    ]

    for jb in job_board_domains:
        if jb in domain:
            # Try path segments
            path_parts = [p for p in parsed.path.split("/") if p and len(p) > 2]
            if path_parts:
                # First meaningful path segment is often the company
                company = path_parts[0].replace("-", " ").replace("_", " ")
                return company.title()

    # Direct company site – use the domain
    company = domain.split(".")[0].replace("-", " ").replace("_", " ")
    return company.title()


# ──────────────────────────────────────────────
# 9. UTILITY: SEARCH FOR HIRING EMAIL
# ──────────────────────────────────────────────
def search_hiring_email(company_name: str, job_url: str = "", jd_text: str = "") -> str:
    """
    Finds a hiring manager or recruiter email using a mini ReAct loop.
    1. Initial regex check on JD.
    2. LiteLLMAgent "Investigator" loop with SEARCH and READ tools.
    """
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    
    # 1. Initial Check
    if jd_text:
        found = email_pattern.findall(jd_text)
        for email in found:
            email = email.lower()
            if not any(bad in email for bad in ["example.com", "test.com", "noreply", "no-reply", "donotreply", "sentry"]):
                logger.info(f"[Investigator] Found contact email directly in JD: {email}")
                return email

    # 2. Initialize Agent
    investigator = LiteLLMAgent(
        name="Investigator",
        sys_prompt=(
            f"You are an OSINT Investigator looking for the hiring manager or recruiter email of {company_name}. "
            "You have two tools available:\n"
            "- Action: SEARCH | Target: <query>\n"
            "- Action: READ | Target: <url>\n\n"
            "If you find the email, return ONLY the email address. "
            "If you need more information, use one of the actions above. "
            "Limit your reasoning and be concise."
        ),
        model_config_name="dispatcher_model_config", # Uses groq/qwen3-32b
        use_memory=True
    )

    # 3. The Loop
    prompt = f"Find the verified hiring email for {company_name}. Job URL context: {job_url}"
    msg = Msg(name="user", content=prompt, role="user")

    for i in range(3):
        try:
            reply = investigator(msg)
            content = reply.content
            
            # Check if email is found and no more actions are requested
            if "@" in content and "Action:" not in content:
                found = email_pattern.search(content)
                if found:
                    email = found.group(0).lower()
                    if not any(bad in email for bad in ["example.com", "test.com", "noreply", "no-reply", "donotreply", "sentry"]):
                        logger.info(f"[Investigator] Verified email found after {i+1} steps: {email}")
                        return email

            # Parse and execute Actions
            if "Action: SEARCH" in content:
                # Extract target query
                target = content.split("Target:")[1].split("\n")[0].strip()
                logger.info(f"[Investigator] Step {i+1}: Searching for '{target}'")
                observation = searxng_search(target)
                msg = Msg(name="user", content=f"Search Results:\n{observation}", role="user")
                
            elif "Action: READ" in content:
                # Extract target URL
                target = content.split("Target:")[1].split("\n")[0].strip()
                logger.info(f"[Investigator] Step {i+1}: Reading page {target}")
                observation = crawl_page(target)
                msg = Msg(name="user", content=f"Page Content (Markdown):\n{observation}", role="user")
            
            else:
                # Fallback extraction if format is slightly off
                found = email_pattern.search(content)
                if found:
                    return found.group(0).lower()
                break
                
        except Exception as e:
            logger.error(f"[Investigator] Loop error at step {i+1}: {e}")
            break

    logger.warning(f"[Investigator] No verified hiring email found for {company_name} after ReAct loop.")
    return "Not Found"
