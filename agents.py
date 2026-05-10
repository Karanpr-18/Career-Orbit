"""
agents.py – AgentScope agent definitions for the Multi-Agent Job Hunter.

Defines four agents:
  A. The Scout       – Finds new job postings across the web
  B. The Architect   – Scores JDs and routes actions
  C. The Ghostwriter – Drafts human-sounding cold emails
  D. The Dispatcher  – Executes Playwright apply, Gmail drafts, CSV tracking
"""

import json
import logging
from agentscope.message import Msg
import litellm
import os
from config import KARAN_PROFILE, MODEL_CONFIGS

class LiteLLMAgent:
    """A lightweight replacement for DialogAgent using LiteLLM directly."""
    def __init__(self, name, sys_prompt, model_config_name, use_memory=True):
        self.name = name
        self.sys_prompt = sys_prompt
        # Find the actual litellm model name from config
        self.model = next((cfg["model_name"] for cfg in MODEL_CONFIGS if cfg["config_name"] == model_config_name), "groq/llama-3.1-8b-instant")
        self.use_memory = use_memory
        self.memory = [{"role": "system", "content": self.sys_prompt}]

    def __call__(self, msg: Msg) -> Msg:
        self.memory.append({"role": "user", "content": msg.content})
        
        # Groq API call via litellm
        response = litellm.completion(
            model=self.model,
            messages=self.memory,
            api_key=os.environ.get("GROQ_API_KEY")
        )
        
        reply_text = response.choices[0].message.content
        
        if self.use_memory:
            self.memory.append({"role": "assistant", "content": reply_text})
        else:
            # Drop user message if no memory
            self.memory.pop()
            
        return Msg(name=self.name, content=reply_text, role="assistant")


from config import KARAN_PROFILE

logger = logging.getLogger("job_hunter.agents")


# ══════════════════════════════════════════════
# AGENT A: THE SCOUT
# ══════════════════════════════════════════════
SCOUT_SYS_PROMPT = """You are The Scout – a job search specialist.

YOUR TASK:
Search the internet for AI/ML internship job postings in India posted in the last 10 days.

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
# AGENT D: THE DISPATCHER
# ══════════════════════════════════════════════
DISPATCHER_SYS_PROMPT = """You are The Dispatcher – a precision execution agent.

You receive structured instructions and execute them using the available tools. You DO NOT make creative decisions. You follow the plan exactly.

YOUR TOOLS:
1. playwright_apply – Fill application forms on Greenhouse/Lever/Workable portals
2. gmail_draft_email – Create a Gmail draft with the cold email
3. append_to_tracker – Log the result to tracker.csv
4. search_hiring_email – Search the web for a recruiter/hiring email

EXECUTION RULES:
- If action is "PLAYWRIGHT_APPLY": Try Playwright first. If it fails (login wall, error), fall back to cold email.
- If action is "SKIP_TO_EMAIL": Go directly to email drafting.
- If action is "SKIP": Only append to tracker with status "Skipped (Low Fit Score: <7)".
- ALWAYS append to tracker after every action, regardless of outcome.

For EACH job, report your result as a JSON:
{
  "company": "...",
  "role": "...",
  "url": "...",
  "portal_status": "...",
  "email_sent_to": "...",
  "application_status": "...",
  "details": "..."
}
"""


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
    )


def create_dispatcher_agent():
    return LiteLLMAgent(
        name="The Dispatcher",
        sys_prompt=DISPATCHER_SYS_PROMPT,
        model_config_name="dispatcher_model_config",
        use_memory=False,
    )
