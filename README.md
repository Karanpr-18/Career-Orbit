# Career-Orbit 🚀
### *The Next-Gen Autonomous AI Agentic Job Search Engine*

[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Groq](https://img.shields.io/badge/Groq-LPU_Powered-orange?style=for-the-badge)](https://groq.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**Career-Orbit** is a sophisticated multi-agent system designed to automate the most time-consuming aspects of the job hunt: lead discovery, technical alignment review, and personalized outreach. By leveraging the speed of Groq's LPU and the flexibility of AgentScope, Career-Orbit acts as a full-time, autonomous career agent on your desktop.

---

## 🏛️ System Architecture

Career-Orbit operates on a distributed multi-agent architecture where specialized AI entities collaborate in a strictly governed pipeline.

### 🧠 The Core Agent Team

| Agent | Responsibility | Core Logic |
| :--- | :--- | :--- |
| **🔍 Scout** | **Market Intelligence** | Scans 15+ job boards using recursive search queries. Filters for entry-level/intern roles in India & Remote. |
| **🏗️ Architect** | **Technical Alignment** | Scores JDs against CV using RAG-like matching. Evaluates tech stack, publications, and proof-of-work. |
| **✍️ Ghostwriter** | **Strategic Outreach** | Crafts personalized cold emails with "Gen-Z Professional" tone. Enforces strict word limits and professional formatting. |
| **🤖 Assistant** | **User Interaction** | Real-time chat assistant inside the dashboard to answer system queries and provide hunt insights. |

### 🛠️ The Pipeline Workflow
1.  **Discovery Phase**: Scout gathers raw URLs from Instahyre, Wellfound, LinkedIn, and Career Portals.
2.  **Filtration Phase**: LLM-based first-pass filtering removes mismatched roles (Senior/Managerial).
3.  **Deep Review**: Architect scores roles (0-10) based on `config.py` and your `resume.pdf`.
4.  **Drafting**: Ghostwriter generates highly specific email drafts using Gmail API.
5.  **Tracking**: Real-time logging to `tracker.csv` and `agent_status.json`.

---

## 🖥️ Career-Orbit Dashboard (Next.js)

The project includes a premium, glassmorphism-inspired command center built with **Next.js 15**.

-   **Autonomous Control**: Side-by-side Start/Stop controls with immediate process state verification.
-   **Live CLI Terminal**: A high-fidelity log viewer that streams agent decision-making logic.
-   **Progress Analytics**: Visual tracking of search depth and mailing throughput.
-   **Application Tracker**: A managed UI to update application statuses (Mailed, Interview, Accepted) directly to the CSV.

---

## 📂 Project Structure

```bash
Careerorbit/
├── app/                # Next.js 15 Dashboard (Frontend)
│   ├── api/            # Backend API Routes (Agent & Job Management)
│   └── globals.css     # Premium UI Design System
├── agents.py           # Multi-Agent Definitions (AgentScope)
├── job_hunter.py       # Main Pipeline Orchestration
├── tools.py            # Low-level Tools (Search, Scrape, Gmail, Playwright)
├── config.py           # Central Configuration & Target Parameters
├── tracker.csv         # Persistent Application Database
└── .env                # Secure Environment Configuration
```

---

## ⚡ Installation & Deployment

### 1. Python Environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Frontend Setup
```bash
npm install
npm run dev
```

### 3. API Configuration
Ensure your `.env` contains:
- `GROQ_API_KEY`: Groq Cloud API Key.
- `RESUME_PATH`: Absolute path to your resume PDF.
- `TRACKER_CSV_PATH`: Path to the local `tracker.csv`.

---

## ⚙️ Advanced Configuration

### Broadening the Search Funnel
In `config.py`, you can modify `TARGET_SITES` and `SEARCH_QUERIES`. The system is currently optimized for:
-   **Roles**: AI/ML, Data Science, Python, Research.
-   **Level**: Internships, Junior, Associate.
-   **Window**: Last 15 days.

### Outreach Strategy
The **Ghostwriter** is programmed to use a professional yet modern tone. You can adjust the signature and proof-of-work highlights in `agents.py` to match your personal brand.

---

## 🔒 Security & Best Practices

-   **Gmail OAuth2**: Career-Orbit uses official Google OAuth2 protocols (`credentials.json`) for secure email drafting.
-   **Rate Limiting**: Automated delays and system-status checks prevent IP flagging and API quota exhaustion.
-   **Local Intelligence**: All your application data and personal documents remain on your local filesystem.

---

## 🤝 Contributing

We welcome contributions to broaden Career-Orbit's capabilities. 
1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

*Career-Orbit — Transforming the job hunt from a full-time job into a background process.*
