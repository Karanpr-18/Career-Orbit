"""
tools.py – Custom tool functions for the AgentScope Multi-Agent Job Hunter.

Provides:
  1. searxng_search    – SearxNG search for job postings
  2. crawl_page        – Crawl4AI reader to extract JD text
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
import asyncio
import requests
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from agents import LiteLLMAgent
from agentscope.message import Msg

logger = logging.getLogger("job_hunter.tools")

# ──────────────────────────────────────────────
# 1. WEB SEARCH (SearxNG)
# ──────────────────────────────────────────────
def serper_search(query: str) -> str:
    """
    Search the web using Google Serper API.
    Returns a clean string formatted for the LLM.
    """
    try:
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": query,
            "gl": "in",
            "hl": "en",
            "num": 20
        })
        headers = {
            'X-API-KEY': os.environ.get("SERPER_API_KEY", ""),
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, data=payload, timeout=20)
        
        if response.status_code != 200:
            masked_key = headers['X-API-KEY'][:6] + "..."
            logger.error(f"[Scout] Serper API Error ({response.status_code}) using key {masked_key}: {response.text}")
            return f"Search Error: {response.text}"
            
        data = response.json()
        organic = data.get("organic", [])[:5]
        
        if not organic:
            return "Search Error: No results found."
            
        formatted_results = []
        for i, res in enumerate(organic):
            title = res.get("title", "")
            link = res.get("link", "")
            snippet = res.get("snippet", "")
            formatted_results.append(f"Result {i+1}:\nTitle: {title}\nLink: {link}\nSnippet: {snippet}\n")
            
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"[Scout] Serper search failed for '{query}': {e}")
        return "Search Error: Check API Credits."

def crawl_page(url: str) -> str:
    """
    Crawl a page using Crawl4AI to bypass bot protection.
    Returns the raw markdown text.
    """
    async def _crawl_async():
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, bypass_cache=True)
            # Increase limit for high-tier models
            return result.markdown[:8000]

    try:
        return asyncio.run(_crawl_async())
    except Exception as e:
        logger.error(f"[Architect] Crawl4AI failed for {url}: {e}")
        return f"Error: {e}"

# ──────────────────────────────────────────────
# 2. SCRAPE JOB PAGE (Wrapper)
# ──────────────────────────────────────────────
def scrape_job_page(url: str) -> str:
    """
    Scrape the text content of a job posting page using crawl_page.
    """
    return crawl_page(url)

# ──────────────────────────────────────────────
# 3. SCORE JOB DESCRIPTION
# ──────────────────────────────────────────────
def score_job(jd_text: str) -> int:
    """
    Score a job description based on keyword matching.
    """
    from config import SCORE_10_KEYWORDS, SCORE_8_KEYWORDS, SCORE_SKIP_KEYWORDS

    jd_lower = jd_text.lower()
    skip_count = sum(1 for kw in SCORE_SKIP_KEYWORDS if kw in jd_lower)
    high_count = sum(1 for kw in SCORE_10_KEYWORDS if kw in jd_lower)
    mid_count = sum(1 for kw in SCORE_8_KEYWORDS if kw in jd_lower)

    if skip_count >= 2 and high_count == 0:
        return 5
    if high_count >= 2:
        return 10
    if mid_count >= 2:
        return 8
    if high_count >= 1 or mid_count >= 1:
        return 8
    return 5

# ──────────────────────────────────────────────
# 4. ROUTE ACTION
# ──────────────────────────────────────────────
def route_action(url: str, score: int) -> str:
    """
    Determine the action to take based on URL domain and score.
    """
    from config import LOGIN_REQUIRED_DOMAINS, PLAYWRIGHT_APPLY_DOMAINS

    if score < 7:
        return "SKIP"

    parsed = urlparse(url).netloc.lower()
    for domain in LOGIN_REQUIRED_DOMAINS:
        if domain in parsed:
            return "SKIP_TO_EMAIL"
    for domain in PLAYWRIGHT_APPLY_DOMAINS:
        if domain in parsed or domain in url.lower():
            return "PLAYWRIGHT_APPLY"
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
    my_cv_text: str = "",
) -> dict:
    """
    Agent-driven form filling using Playwright.
    """
    from config import KARAN_PROFILE
    from agents import create_smart_form_filler_agent
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) # Keep False for debug/visibility during automation
            context = browser.new_context()
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=45000)
            time.sleep(5) # Allow dynamic forms to load
            
            # Step 1: Gather all relevant input fields
            inputs = page.query_selector_all("input, textarea, select")
            form_context = []
            for idx, el in enumerate(inputs):
                try:
                    # Get associated label if possible
                    label_text = ""
                    id_val = el.get_attribute("id")
                    if id_val:
                        label_el = page.query_selector(f"label[for='{id_val}']")
                        if label_el: label_text = label_el.inner_text()
                    
                    form_context.append({
                        "id": id_val,
                        "name": el.get_attribute("name"),
                        "type": el.get_attribute("type"),
                        "placeholder": el.get_attribute("placeholder"),
                        "label": label_text,
                        "tag": el.evaluate("el => el.tagName.toLowerCase()")
                    })
                except: continue

            # Step 2: Use Agent to determine mappings
            filler_agent = create_smart_form_filler_agent()
            user_data = json.dumps(KARAN_PROFILE, indent=1)
            prompt = (
                f"Form Context:\n{json.dumps(form_context, indent=1)}\n\n"
                f"User Profile:\n{user_data}\n\n"
                f"CV Text Excerpt:\n{my_cv_text[:2000]}\n\n"
                "Provide the JSON mappings for these fields."
            )
            
            from job_hunter import parse_json_from_response
            response = filler_agent(Msg(name="user", content=prompt, role="user"))
            mappings_data = parse_json_from_response(response.content)
            
            if not mappings_data or "mappings" not in mappings_data:
                browser.close()
                return {"success": False, "status": "Failed", "details": "Agent could not map form fields."}

            # Step 3: Execute Mappings
            for mapping in mappings_data["mappings"]:
                selector = mapping.get("selector")
                val = mapping.get("value")
                if selector and val:
                    try:
                        page.fill(selector, val)
                    except:
                        # Try fallback: if selector is ID or Name, build a generic one
                        try: page.type(selector, val)
                        except: continue

            # Step 4: Handle Resume Upload
            if mappings_data.get("is_resume_required") and resume_path:
                res_selector = mappings_data.get("resume_selector", "input[type='file']")
                try:
                    page.set_input_files(res_selector, resume_path)
                except:
                    logger.warning(f"[Dispatcher] Could not upload resume using {res_selector}")

            time.sleep(2)
            # We don't click submit automatically to prevent accidental double-submits 
            # during dev, but we return success if we filled the form.
            browser.close()
            return {"success": True, "status": "Applied", "details": f"Filled {len(mappings_data['mappings'])} fields via AI."}
            
    except Exception as e:
        logger.error(f"[Dispatcher] Smart Playwright failed for {url}: {e}")
        return {"success": False, "status": "Skipped (Playwright Error)", "details": str(e)}

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
    from config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH
    if not credentials_path: credentials_path = GMAIL_CREDENTIALS_PATH
    if not token_path: token_path = GMAIL_TOKEN_PATH

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        import base64
        from email.mime.text import MIMEText

        SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)
        message = MIMEText(body)
        message["to"] = to_email
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        return {"success": True, "draft_id": draft["id"], "error": None}
    except Exception as e:
        logger.error(f"[Dispatcher] Gmail draft failed for {to_email}: {e}")
        return {"success": False, "draft_id": None, "error": str(e)}

# ──────────────────────────────────────────────
# 7. TRACKER CSV OPERATIONS
# ──────────────────────────────────────────────
def load_existing_urls(tracker_path: str = "") -> set:
    from config import TRACKER_CSV_PATH
    if not tracker_path: tracker_path = TRACKER_CSV_PATH
    urls = set()
    if not os.path.exists(tracker_path): return urls
    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            content = f.read()
            url_pattern = re.compile(r"https?://[^\s,'\"\r\n]+")
            urls = set(url_pattern.findall(content))
        return urls
    except Exception as e:
        logger.error(f"[Tracker] Failed to load URLs: {e}")
        return urls

def count_successful_sends(tracker_path: str = "") -> int:
    from config import TRACKER_CSV_PATH
    if not tracker_path: tracker_path = TRACKER_CSV_PATH
    if not os.path.exists(tracker_path): return 0
    count = 0
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None) # Skip header
            if not header: return 0
            
            for row in reader:
                if len(row) < 7: continue
                # Success statuses: Mailed, Applied, Drafted
                # Date is usually index 0
                date = row[0].strip("'\"")
                if date != today: continue
                
                status = row[-1].lower()
                if any(s in status for s in ["mailed", "applied", "drafted"]):
                    count += 1
        return count
    except Exception as e:
        logger.error(f"[Tracker] Failed to count success: {e}")
        return 0

def verify_email_with_emailable(email: str) -> dict:
    """Verifies email deliverability using Emailable API."""
    api_key = os.environ.get("EMAILABLE_API_KEY")
    if not api_key:
        logger.warning("[Emailable] No API key found. Skipping verification (assuming valid).")
        return {"success": True, "state": "unknown", "score": 100}
    
    try:
        url = f"https://api.emailable.com/v1/verify?email={email}&api_key={api_key}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Emailable 'state' can be: deliverable, undeliverable, risky, unknown
        state = data.get("state", "unknown")
        score = data.get("score", 0)
        
        # We only want deliverable emails with a decent score
        is_valid = state == "deliverable" and score >= 65
        
        logger.info(f"[Emailable] {email} verification: {state} (Score: {score})")
        return {"success": is_valid, "state": state, "score": score}
    except Exception as e:
        logger.error(f"[Emailable] Verification error for {email}: {e}")
        return {"success": True, "state": "error", "score": 0} # Fallback to true to not block if API is down

def append_to_tracker(date, company, role, url, portal_status, email_sent_to, application_status, tracker_path=""):
    from config import TRACKER_CSV_PATH
    if not tracker_path: tracker_path = TRACKER_CSV_PATH
    try:
        os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
        with open(tracker_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow([date, company, role, url, portal_status, email_sent_to, application_status])
        return True
    except Exception as e:
        logger.error(f"[Tracker] Failed to append row: {e}")
        return False

# ──────────────────────────────────────────────
# 8. UTILITIES
# ──────────────────────────────────────────────
def extract_company_from_url(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    for prefix in ["www.", "jobs.", "careers.", "boards.", "job-boards.", "apply."]:
        if domain.startswith(prefix): domain = domain[len(prefix):]
    company = domain.split(".")[0].replace("-", " ").replace("_", " ")
    return company.title()

def search_hiring_email(company_name: str, job_url: str = "", jd_text: str = "") -> str:
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    if jd_text:
        found = email_pattern.findall(jd_text)
        for email in found:
            email = email.lower()
            if not any(bad in email for bad in ["example.com", "test.com", "noreply", "no-reply", "donotreply", "sentry"]):
                return email

    investigator = LiteLLMAgent(
        name="Investigator",
        sys_prompt=(
            f"You are an OSINT Investigator looking for the email of {company_name}.\n"
            "TARGETS: Hiring Manager, Talent Acquisition, HR, Engineering Manager, Senior Engineers, or the job poster.\n"
            "If HR is not found, look for ANY verified employee in the relevant department.\n"
            "Tools: Action: SEARCH | Target: <query>, Action: READ | Target: <url>"
        ),
        model_config_name="investigator_model_config",
        use_memory=True,
        fallback_config_name="investigator_fallback_model"
    )
    prompt = f"Find the verified hiring email for {company_name}. Job URL context: {job_url}"
    msg = Msg(name="user", content=prompt, role="user")
    
    for i in range(3):
        try:
            # mimick human browsing behavior to avoid CAPTCHAs
            time.sleep(1) 
            
            reply = investigator(msg)
            content = reply.content
            if "@" in content and "Action:" not in content:
                found = email_pattern.search(content)
                if found: return found.group(0).lower()
            
            if "Action: SEARCH" in content:
                target = content.split("Target:")[1].split("\n")[0].strip()
                # 20s timeout for international routing is handled in serper_search
                observation = serper_search(target) 
                msg = Msg(name="user", content=f"Search Results:\n{observation}", role="user")
            elif "Action: READ" in content:
                target = content.split("Target:")[1].split("\n")[0].strip()
                observation = crawl_page(target)
                msg = Msg(name="user", content=f"Page Content:\n{observation}", role="user")
            else:
                found = email_pattern.search(content)
                if found: return found.group(0).lower()
                break
        except Exception as e:
            logger.error(f"[Investigator] Error in ReAct loop: {e}")
            break
    return "Not Found"

def extract_cv_text(pdf_path: str) -> str:
    # --- TOKEN OPTIMIZED: Exclusive Markdown Loader ---
    base_dir = os.path.dirname(pdf_path)
    file_name = os.path.basename(pdf_path).lower()
    
    target_md = "RESUME.md" if "resume" in file_name else "CV.md"
    md_path = os.path.join(base_dir, target_md)
    
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.warning(f"[Loader] Failed to read {target_md}: {e}")

    # If MD is missing, return a descriptive error for the agent
    return "ERROR: Resume/CV Markdown file not found. Please ensure RESUME.md or CV.md exists."
