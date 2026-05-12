import os
import litellm
from dotenv import load_dotenv

load_dotenv()
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")

try:
    models = litellm.get_valid_models("groq")
    print("Valid Groq models according to LiteLLM:")
    for m in models:
        if "qwen" in m.lower():
            print(f"- {m}")
except Exception as e:
    print(f"Error: {e}")
