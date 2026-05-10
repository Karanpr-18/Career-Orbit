"""
config.py – Central configuration for the AgentScope Multi-Agent Job Hunter.

Loads environment variables, defines model configs for Groq via LiteLLM,
and sets all file paths and constants used across the system.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
os.environ["GROQ_API_KEY"] = GROQ_API_KEY  # LiteLLM picks this up automatically

# ──────────────────────────────────────────────
# File Paths
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESUME_PATH = os.getenv("RESUME_PATH", os.path.join(BASE_DIR, "my_resume.pdf"))
CV_PATH = os.getenv("CV_PATH", os.path.join(BASE_DIR, "my_cv.pdf"))
TRACKER_CSV_PATH = os.path.join(BASE_DIR, "tracker.csv")
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", os.path.join(BASE_DIR, "credentials.json"))
GMAIL_TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
INTERN_AGENT_PROMPT_PATH = os.path.join(BASE_DIR, "intern_agent.md")

# ──────────────────────────────────────────────
# Rate Limiting & Scheduling
# ──────────────────────────────────────────────
MAX_APPLICATIONS_PER_DAY = int(os.getenv("MAX_APPLICATIONS_PER_DAY", "50"))
DELAY_BETWEEN_APPLICATIONS = int(os.getenv("DELAY_BETWEEN_APPLICATIONS_SECONDS", "0"))
WORK_HOURS_START = int(os.getenv("WORK_HOURS_START", "9"))
WORK_HOURS_END = int(os.getenv("WORK_HOURS_END", "17"))

# ──────────────────────────────────────────────
# Job Search Queries
# ──────────────────────────────────────────────
SEARCH_QUERIES = [
    "AI Engineer Intern India",
    "ML Intern India",
    "Data Science Intern India",
    "Machine Learning Intern India",
    "GenAI Intern India",
    "Deep Learning Intern India",
    "NLP Intern India",
    "LLM Engineer Intern India",
]

TARGET_SITES = [
    "instahyre.com",
    "wellfound.com",
    "linkedin.com",
    "naukri.com",
    "workable.com",
    "greenhouse.io",
    "lever.co",
    "workatastartup.com",
    "angel.co",
    "internshala.com",
]

# Sites that typically require login – skip form filling, email instead
LOGIN_REQUIRED_DOMAINS = [
    "linkedin.com",
    "naukri.com",
    "instahyre.com",
    "wellfound.com",
    "internshala.com",
    "angel.co",
]

# Sites where Playwright form-fill is attempted
PLAYWRIGHT_APPLY_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "workable.com",
    "applytojob.com",
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "apply.workable.com",
]

# ──────────────────────────────────────────────
# Scoring Keywords
# ──────────────────────────────────────────────
SCORE_10_KEYWORDS = [
    "llm", "llms", "large language model", "pytorch", "model optimization",
    "transformers", "huggingface", "fine-tuning", "fine tuning", "rlhf",
    "langchain", "llamaindex", "rag", "retrieval augmented", "agentic",
    "prompt engineering",
]

SCORE_8_KEYWORDS = [
    "scikit-learn", "sklearn", "sql", "python", "pandas", "numpy",
    "data science", "machine learning", "tensorflow", "keras",
    "statistical", "regression", "classification",
]

SCORE_SKIP_KEYWORDS = [
    "excel", "power bi", "tableau", "data analyst", "business analyst",
    "data entry", "mis reporting", "advanced excel",
]

# ──────────────────────────────────────────────
# Tracker CSV Columns
# ──────────────────────────────────────────────
TRACKER_COLUMNS = [
    "Date",
    "Company",
    "Role",
    "URL",
    "Portal Status",
    "Cold Email Sent To",
    "Application Status",
]

# ──────────────────────────────────────────────
# AgentScope Model Configurations (Groq via LiteLLM)
# ──────────────────────────────────────────────
MODEL_CONFIGS = [
    {
        "config_name": "scout_model_config",
        "model_type": "litellm_chat",
        "model_name": "groq/llama-3.1-8b-instant",
        "generate_args": {
            "temperature": 0.3,
            "max_tokens": 4096,
        },
    },
    {
        "config_name": "architect_model_config",
        "model_type": "litellm_chat",
        "model_name": "groq/llama-3.3-70b-versatile",
        "generate_args": {
            "temperature": 0.2,
            "max_tokens": 4096,
        },
    },
    {
        "config_name": "architect_fallback_model",
        "model_type": "litellm_chat",
        "model_name": "groq/qwen-qwq-32b",
        "generate_args": {
            "temperature": 0.2,
            "max_tokens": 4096,
        },
    },
    {
        "config_name": "ghostwriter_model_config",
        "model_type": "litellm_chat",
        "model_name": "groq/llama-3.3-70b-versatile",
        "generate_args": {
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    },
    {
        "config_name": "dispatcher_model_config",
        "model_type": "litellm_chat",
        "model_name": "openai/gpt-oss-120b",
        "generate_args": {
            "temperature": 0.1,
            "max_tokens": 4096,
        },
    },
]

# ──────────────────────────────────────────────
# Ghostwriter Context (Karan's profile for cold emails)
# ──────────────────────────────────────────────
KARAN_PROFILE = {
    "name": "Karan Bhoriya",
    "university": "Sushant University",
    "degree": "B.Tech CSE (AIML)",
    "phone": "",  # Fill in if you want it included in forms
    "email": "",  # Fill in your email address
    "resume_link": "https://drive.google.com/file/d/1XDO1bhwvr4bN2mbAbUhvGoEort3W7UVf/view?usp=sharing",
    "cv_link": "https://drive.google.com/file/d/1MAfe5EFtl8QGtTe6M8KZRviEF1iA6CV1/view?usp=sharing",
    "portfolio_link": "https://karanpr-18.github.io/Karan-Portfolio/",
    "projects": {
        "genai_nlp_llm": {
            "name": "TalentAI",
            "desc": "end-to-end recruitment platform using Python, Flask, Groq Llama 3.1, and Gemini Pro for resume parsing",
        },
        "deep_learning": {
            "name": "Next Word Prediction",
            "desc": "built from scratch in PyTorch with custom LSTM architecture",
        },
        "data_pipelines": {
            "name": "Humana Data Analyst Internship",
            "desc": "engineered Python validation pipelines that cut QA time from 4 days to 2 hours",
        },
        "classical_ml_research": {
            "name": "GoEmotions Research",
            "desc": "evaluating Random Forest/LinearSVC on a 58K emotion-labeled dataset",
        },
    },
    "mandatory_signoff": """
---
**Links:**
* **Resume:** https://drive.google.com/file/d/1XDO1bhwvr4bN2mbAbUhvGoEort3W7UVf/view?usp=sharing
* **Full CV & Research:** https://drive.google.com/file/d/1MAfe5EFtl8QGtTe6M8KZRviEF1iA6CV1/view?usp=sharing
* **Portfolio & Projects:** https://karanpr-18.github.io/Karan-Portfolio/
""",
}
