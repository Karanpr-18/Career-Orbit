# 🚀 Career-Orbit: The Autonomous Agentic Job Portal

**Career-Orbit** is a state-of-the-art, multi-agent AI pipeline designed to automate the high-volume outreach phase of internship and entry-level job hunting. Powered by **Groq-hosted open-source models** and orchestrated through a premium **Next.js Dashboard**, it transforms the tedious process of job searching into a streamlined, autonomous operation.

---

## 🛠️ The Agentic Architecture

Career-Orbit utilizes a specialized team of three AI agents that work in sequence to find, evaluate, and apply for roles:

1.  **🔍 The Scout**: Scans 15+ major job boards (instahyre, wellfound, linkedin, etc.) using broad, high-signal queries. It filters out senior roles and identifies potential matches for students and junior engineers.
2.  **🏗️ The Architect**: Performs a deep-dive analysis of each job description. It scores the role against your specific resume, tech stack, and publications, ensuring a high-quality match.
3.  **✍️ The Ghostwriter**: Drafts personalized, high-impact cold emails. It uses a "Gen-Z Professional" tone, respects a strict 100-word limit, and ensures professional formatting with double-newline spacing.

---

## ✨ Key Features

-   **Autonomous Pipeline**: Full end-to-end automation from lead discovery to Gmail draft creation.
-   **Premium Dashboard**: A modern, glassmorphism-inspired interface to monitor agent status, progress, and logs in real-time.
-   **Broad Search Discovery**: Targets major platforms including Indeed, Glassdoor, Internshala, and corporate career portals (Greenhouse, Lever, Ashby).
-   **Real-time CLI Terminal**: Integrated log viewer in the dashboard to watch the agents' decision-making process live.
-   **Smart Tracker**: Automatically records every discovery and outreach in a local `tracker.csv` for easy management.

---

## 🚀 Quick Start

### 1. Prerequisites
-   **Python 3.10+**
-   **Node.js 18+**
-   **Groq API Key**: For lightning-fast AI inference.
-   **Gmail API Credentials**: `credentials.json` from Google Cloud Console.

### 2. Environment Setup
Create a `.env` file in the root directory:
```bash
GROQ_API_KEY=your_key_here
RESUME_PATH=/path/to/your_resume.pdf
CV_PATH=/path/to/your_cv.pdf
TRACKER_CSV_PATH=/path/to/Careerorbit/tracker.csv
```

### 3. Installation
```bash
# Install Python dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Dashboard dependencies
npm install
```

### 4. Running the System
```bash
# Start the Dashboard
npm run dev
```
Navigate to `http://localhost:3000` to access the **Career-Orbit Command Center**.

---

## 🕹️ Dashboard Controls

-   **Start Button**: Initializes the agentic pipeline in the background. It checks for stale processes and ensures a fresh run every time.
-   **Stop Button**: Immediately terminates the agent using `SIGKILL` to prevent resource leaks.
-   **Execution Pipeline**: A visual map showing exactly which phase the agent is currently executing (Scouting, Reviewing, or Mailing).
-   **Stats Grid**: Real-time breakdown of Total Leads, Mails Sent, and Application Statuses.

---

## ⚙️ Configuration

You can fine-tune the agents in `config.py`:
-   **SEARCH_QUERIES**: Broaden or narrow your target roles.
-   **TARGET_SITES**: Add or remove specific job boards.
-   **WORK_HOURS**: Restrict the agent to run only during professional hours (default 9 AM - 5 PM).

---

## 🔒 Privacy & Security

-   **Local Data**: Your `tracker.csv` and logs stay on your machine.
-   **No Passwords**: Uses Google OAuth2 (`token.json`) for secure Gmail access—no passwords required.
-   **Rate Limiting**: Includes safety buffers to respect API quotas and prevent automated detection.

---

**Built with ❤️ for the next generation of engineers.**
*Career-Orbit — Automating your journey to the stars.*
