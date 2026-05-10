# 🚀 CareerOrbit: The AI-Powered Multi-Agent Job Hunter

**CareerOrbit** is an advanced, automated job application system that uses a swarm of AI agents to discover, evaluate, and apply for internships and jobs. Built with **AgentScope**, **Next.js**, and **Groq-hosted LLMs**, it transforms the job hunt from a manual grind into a high-precision, automated pipeline.

![Dashboard Preview](https://via.placeholder.com/1200x600?text=CareerOrbit+Dashboard+Preview)

## 🌟 Key Features

- **🧠 Multi-Agent Orchestration**: Four specialized agents (Scout, Architect, Ghostwriter, Dispatcher) working in sync.
- **⚡ Real-time Dashboard**: Monitor agent progress, logs, and application stats in a premium React-based interface.
- **📧 Automated Cold Emails**: Generates highly personalized, context-aware emails for recruiters using Llama 3.3 70B.
- **🤖 Playwright Automation**: Automatically fills out application forms on supported platforms like Greenhouse and Lever.
- **📊 Tracker Integration**: Every application, email, and skip reason is logged in a persistent CSV tracker.
- **💬 Integrated AI Assistant**: A built-in chat interface to query your application data and get system help.

## 🏗️ The Multi-Agent Pipeline

1. **The Scout**: Searches 7+ job boards (LinkedIn, Wellfound, Naukri, etc.) using DuckDuckGo search.
2. **The Architect**: Scrapes job descriptions and scores them against your specific profile and tech stack.
3. **The Ghostwriter**: Drafts short, punchy cold emails that sound human and include your portfolio links.
4. **The Dispatcher**: Executes the final action—either filling a form via Playwright or creating a Gmail draft.

## 🛠️ Tech Stack

- **Frontend**: Next.js 16 (App Router), Tailwind CSS, Lucide Icons.
- **Backend**: Next.js API Routes (Serverless), Python 3.12.
- **AI Framework**: [AgentScope](https://github.com/modelscope/agentscope), [LiteLLM](https://github.com/BerriAI/litellm).
- **LLMs**: Groq (Llama 3.3 70B, Qwen 2.5) for lightning-fast inference.
- **Automation**: Playwright, Gmail API.

## 🚀 Getting Started

Check out the [**SETUP.md**](./SETUP.md) guide for detailed installation instructions.

### Quick Start (Development)
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Run the development server
npm run dev
```

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
Built with ❤️ by [Karan Bhoriya](https://karanpr-18.github.io/Karan-Portfolio/)
