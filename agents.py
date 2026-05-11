"""
agents.py – AgentScope agent definitions for the Multi-Agent Job Hunter.

Defines four agents:
  A. The Scout       – Finds new job postings across the web
  B. The Architect   – Scores JDs and routes actions
  C. The Ghostwriter – Drafts human-sounding cold emails
  D. The Investigator  – Executes Playwright apply, Gmail drafts, CSV tracking
"""

import json
import logging
import time
from agentscope.message import Msg
import litellm
import os
from config import KARAN_PROFILE, MODEL_CONFIGS

# ──────────────────────────────────────────────
# GLOBAL LITELLM SETUP (Local Rate Limiting)
# ──────────────────────────────────────────────
litellm.drop_params = True 

# Define the global rate limits and model mappings for local enforcement
litellm.model_list = [
    {
        "model_name": "groq/meta-llama/llama-4-scout-17b-16e-instruct",
        "litellm_params": {"model": "groq/qwen-2.5-coder-32b", "rpm": 30,"tpm":"30K", "tpd":"500K"}
    },
    {
        "model_name": "groq/qwen/qwen3-32b",
        "litellm_params": {"model": "groq/qwen-2.5-32b", "rpm": 60, "tpm":"6K", "tpd":"500K"}
    },
    {
        "model_name": "groq/openai/gpt-oss-120b",
        "litellm_params": {"model": "groq/openai/gpt-oss-120b", "rpm": 30, "tpm":"8K", "tpd":"200K"}
    },
    {
        "model_name": "groq/openai/gpt-oss-120b",
        "litellm_params": {"model": "groq/openai/gpt-oss-20b", "rpm": 30, "tpm":"8K", "tpd":"200K"}
    },
    {
        "model_name": "groq/llama-3.3-70b-versatile",
        "litellm_params": {"model": "groq/llama-3.3-70b-versatile", "rpm": 30, "tpm":"12K", "tpd":"100K"}
    }
]

# Initialize the Router for global rate limiting enforcement
router = litellm.Router(model_list=litellm.model_list)

class LiteLLMAgent:
    """A lightweight replacement for DialogAgent using LiteLLM directly."""
    def __init__(self, name, sys_prompt, model_config_name, use_memory=True, fallback_config_name=None):
        self.name = name
        self.sys_prompt = sys_prompt
        # Find the actual litellm model name and args from config
        config = next((cfg for cfg in MODEL_CONFIGS if cfg["config_name"] == model_config_name), None)
        self.model = config["model_name"] if config else "groq/llama-3.1-8b-instant"
        self.generate_args = config.get("generate_args", {}) if config else {}
        
        # Fallback setup
        self.fallback_model = None
        self.fallback_args = {}
        if fallback_config_name:
            fb_config = next((cfg for cfg in MODEL_CONFIGS if cfg["config_name"] == fallback_config_name), None)
            if fb_config:
                self.fallback_model = fb_config["model_name"]
                self.fallback_args = fb_config.get("generate_args", {})
            
        self.use_memory = use_memory
        self.memory = [{"role": "system", "content": self.sys_prompt}]

    def __call__(self, msg: Msg) -> Msg:
        self.memory.append({"role": "user", "content": msg.content})
        
        # Groq API call via litellm with exponential backoff for resilience
        max_retries = 5
        initial_backoff = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # We use router.completion to enforce TPM/RPM/TPD limits locally
                response = router.completion(
                    model=self.model,
                    messages=self.memory,
                    **self.generate_args
                )
                
                reply_text = response.choices[0].message.content
                
                if self.use_memory:
                    self.memory.append({"role": "assistant", "content": reply_text})
                else:
                    self.memory.pop()
                    
                return Msg(name=self.name, content=reply_text, role="assistant")
                
            except (litellm.RateLimitError, Exception) as e:
                error_msg = str(e)
                # Check for TPD (Tokens Per Day) or other major limits for Dashboard visibility
                if "Tokens Per Day" in error_msg or "daily" in error_msg.lower():
                    logger.critical(f"\n🛑 [LIMIT HIT] {self.model} has exhausted its TOKENS PER DAY (TPD) quota!")
                    logger.critical(f"📊 Model Status: EXHAUSTED | Switching to Fallback Strategy...\n")

                # Catch both specific rate limits and generic failures for stability
                if attempt < max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s, 16s...
                    wait_time = initial_backoff * (2 ** attempt)
                    logger.warning(f"[{self.name}] Call failed: {str(e)[:100]}. Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                elif self.fallback_model and self.model != self.fallback_model:
                    # Final attempt: Try the fallback model via router
                    logger.warning(f"[{self.name}] Primary model failed. Swapping to FALLBACK: {self.fallback_model}")
                    try:
                        response = router.completion(
                            model=self.fallback_model,
                            messages=self.memory,
                            **self.fallback_args
                        )
                        reply_text = response.choices[0].message.content
                        if self.use_memory: self.memory.append({"role": "assistant", "content": reply_text})
                        else: self.memory.pop()
                        return Msg(name=self.name, content=reply_text, role="assistant")
                    except Exception as fe:
                        fe_msg = str(fe)
                        if "Tokens Per Day" in fe_msg or "daily" in fe_msg.lower():
                            logger.critical(f"🚨 [CRITICAL] Fallback model {self.fallback_model} ALSO exhausted its TPD quota!")
                        logger.error(f"[{self.name}] Fallback ALSO failed: {fe_msg}")
                        return Msg(name=self.name, content=f"ERROR: Both primary and fallback models failed. {fe_msg}", role="assistant")
                else:
                    logger.error(f"[{self.name}] Max retries reached. Error: {e}")
                    # Return a safe error message instead of crashing the 50-email loop
                    return Msg(name=self.name, content="ERROR: LLM call failed after multiple retries.", role="assistant")


from config import KARAN_PROFILE

logger = logging.getLogger("job_hunter.agents")


# ══════════════════════════════════════════════
# AGENT A: THE SCOUT
# ══════════════════════════════════════════════
SCOUT_SYS_PROMPT = """You are The Scout – a job search specialist.

YOUR TASK:
Filter and evaluate AI/ML internship job postings in India found via Serper.dev.

SEARCH TARGETS (prioritize but don't limit to):
- instahyre.com, wellfound.com, linkedin.com, naukri.com
- workable.com, greenhouse.io, lever.co, workatastartup.com
- internshala.com, ashbyhq.com, angel.co
- Any other company career pages found via web search

SEARCH QUERIES to use:
- "AI Engineer Intern India"
- "ML Intern India"
- "Data Science Intern India"
- "Machine Learning Intern India"
- "GenAI Intern India"
- "Deep Learning Intern India"

STRICT FILTERS:
- INCLUDE: Internships, Junior roles, Associate roles, and Entry-level positions.
- EXCLUDE: Senior, Lead, Manager, Staff, or Principal roles (e.g., 3+ years experience).
- ONLY roles posted in the last 15 days.
- ONLY roles based in India or remote-friendly for India.

OUTPUT FORMAT:
Return a valid JSON array of objects with these fields:
[
  {"title": "Job Title", "url": "https://full-url-here", "company": "Company Name"},
  ...
]

Return ONLY the JSON array. No explanations, no markdown, no extra text.
If you find no new jobs, return an empty array: []
"""


# ══════════════════════════════════════════════
# AGENT B: THE ARCHITECT
# ══════════════════════════════════════════════
ARCHITECT_SYS_PROMPT = """You are The Architect – a job evaluation and routing specialist.

YOUR TASK:
You will receive a job description text scraped from a URL. You must:

1. SCORE the job based on these rules:
   - Score 10: Mentions LLMs, PyTorch, Model Optimization, Transformers, HuggingFace, RAG, LangChain, Agentic AI, Fine-tuning, RLHF, Prompt Engineering.
   - Score 8: Mentions Scikit-learn, SQL, Python-heavy data science, TensorFlow, Keras, Pandas, Statistical modeling, ML pipelines.
   - Score 8 (AUTO): If the text says "Details could not be scraped due to bot protection", assume it is a valid junior AI/ML role and score it an 8.
   - Score <7: Generic 'Data Analyst' roles, Excel-heavy, Power BI only, Tableau only, Business Analyst, MIS, Data Entry. These should be SKIPPED.

2. ROUTE the action based on the URL:
   - If URL contains 'greenhouse.io', 'lever.co', or 'workable.com': action = "PLAYWRIGHT_APPLY"
   - If URL contains 'linkedin.com', 'naukri.com', 'instahyre.com', or 'wellfound.com': action = "SKIP_TO_EMAIL"
   - If login is detected in the page text: action = "SKIP_TO_EMAIL"
   - If score < 7: action = "SKIP"
   - For any unknown portal: action = "SKIP_TO_EMAIL" (safer default)

3. EXTRACT key details from the JD.

OUTPUT FORMAT (strict JSON only):
{
  "score": 10,
  "action": "PLAYWRIGHT_APPLY",
  "company": "Company Name",
  "role": "Job Title",
  "key_technologies": ["PyTorch", "LLMs", "RAG"],
  "jd_category": "genai_nlp_llm",
  "reason": "One-line justification for the score"
}

For jd_category, pick ONE of:
- "genai_nlp_llm" (GenAI, NLP, LLMs)
- "deep_learning" (Neural networks, PyTorch models)
- "data_pipelines" (Data engineering, ETL, analytics pipelines)
- "classical_ml_research" (Scikit-learn, research, statistical ML)
- "general" (doesn't fit neatly into above)

Return ONLY the JSON object. No markdown, no explanations.
"""


# ══════════════════════════════════════════════
# AGENT C: THE GHOSTWRITER
# ══════════════════════════════════════════════
GHOSTWRITER_SYS_PROMPT = f"""You are The Ghostwriter – an expert in writing hyper-personalized, high-conversion cold emails for Karan Bhoriya.

YOUR GOAL: Write a professional 100-word email with PERFECT structure and spacing.

CRITICAL FORMATTING RULES:
1. **Salutation**: ALWAYS start with "Hi [Name]," or "Hi [Company] Team,".
2. **Spacing**: You MUST use a DOUBLE NEWLINE (\\n\\n) between EVERY block (Salutation, Para 1, Para 2, Para 3, Sign-off).
3. **No Walls of Text**: Each paragraph must be exactly 1-2 sentences. 

STRICT WRITING STYLE:
- **Tone**: Engineering-focused, results-driven, "Gen-Z Professional" (no fluff).
- **Metric**: Mention cutting QA time by 95% at Humana.
- **Projects**: Match the project to the JD (TalentAI, PyTorch, etc.).
- **Research Paper**: If the JD mentions "research", "academic", "publications", etc. then mention the research paper("Emotion classification on GoEmotions).

EMAIL STRUCTURE EXAMPLE:
Subject: [Relevant Subject]

Hi [Name],

[Sentence 1-2: Context & Intent]

[Sentence 3-4: The Proof (Numbers/Metric)]

[Sentence 5-6: The Hook & CTA]

Best regards,
Karan Bhoriya

---
**Links:**
* **Resume:** https://drive.google.com/file/d/1XDO1bhwvr4bN2mbAbUhvGoEort3W7UVf/view?usp=sharing
* **Full CV & Research:** https://drive.google.com/file/d/1MAfe5EFtl8QGtTe6M8KZRviEF1iA6CV1/view?usp=sharing
* **Portfolio & Projects:** https://karanpr-18.github.io/Karan-Portfolio/
"""

# ══════════════════════════════════════════════
# AGENT D: THE SMART FORM FILLER
# ══════════════════════════════════════════════
SMART_FORM_FILLER_SYS_PROMPT = """You are a precision Job Application Assistant.
Your task is to map a user's personal profile and CV to the input fields found on a job application page.

INPUTS:
1. FORM FIELDS: A list of HTML tags (inputs, textareas, buttons) with their IDs, Names, Placeholders, and Labels.
2. USER PROFILE: JSON data about the user (Name, Email, Phone, University, etc.).
3. CV TEXT: Full text of the user's CV.

YOUR TASK:
Determine which value from the USER PROFILE or CV goes into which FORM FIELD.

RULES:
- If a field is 'Full Name', use 'name' from profile.
- User isn't in any company currently. So set 'Current Employer' as N/A.
- If a field asks for 'Summary' or 'Why join us?', draft a 2-sentence response based on the CV.
- If a field asks for 'LinkedIn', 'GitHub', or 'Portfolio', use the corresponding links from the profile.
- Return a JSON object where keys are the 'id' or 'name' of the field, and values are the text to type.

OUTPUT FORMAT (strict JSON):
{
  "mappings": [
    {"selector": "#first_name", "value": "Karan"},
    {"selector": "input[name='email']", "value": "karan@example.com"},
    ...
  ],
  "is_resume_required": true,
  "resume_selector": "#resume-upload"
}
"""


def create_smart_form_filler_agent():
    return LiteLLMAgent(
        name="FormFiller",
        sys_prompt=SMART_FORM_FILLER_SYS_PROMPT,
        model_config_name="smart_form_filler_config",
        use_memory=False,
        fallback_config_name="smart_form_filler_fallback"
    )


def create_scout_agent():
    return LiteLLMAgent(
        name="The Scout",
        sys_prompt=SCOUT_SYS_PROMPT,
        model_config_name="scout_model_config",
        use_memory=False,  # Single-shot analysis per batch
    )


def create_architect_agent():
    return LiteLLMAgent(
        name="The Architect",
        sys_prompt=ARCHITECT_SYS_PROMPT,
        model_config_name="architect_model_config",
        use_memory=False,
    )


def create_ghostwriter_agent():
    return LiteLLMAgent(
        name="The Ghostwriter",
        sys_prompt=GHOSTWRITER_SYS_PROMPT,
        model_config_name="ghostwriter_model_config",
        use_memory=False,
        fallback_config_name="ghostwriter_fallback_model"
    )
