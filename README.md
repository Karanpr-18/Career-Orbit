<div align="center">
  
# Career-Orbit 🚀
### *Your Personal Multi-Agent AI Job Hunting Team*

[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![Groq](https://img.shields.io/badge/Groq-LPU_Powered-orange)](https://groq.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Automation-green?logo=playwright)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Career-Orbit** is an open-source platform that turns the exhausting process of job hunting into an automated, background operation. It gives you a team of specialized AI agents that find jobs, evaluate if you are a good fit, fill out applications, and draft personalized cold emails on your behalf.

</div>

---

## 🤔 The Problem vs. The Solution

**The Problem:** Job hunting is a full-time job. You spend hours searching LinkedIn, reading through dense job descriptions, deciding if you are qualified, typing your details into identical portal forms, and writing cover letters.

**The Solution:** Career-Orbit automates the entire funnel. You start the system, and it runs in the background. It reads your CV once, understands your skills, and then scours the internet applying for jobs and drafting emails that sound exactly like you wrote them.

---

## 🤖 How It Works: Meet Your AI Team

Career-Orbit isn't just one big script; it is a team of four distinct AI "employees" working together:

### 1. 🔍 The Scout (The Researcher)
The Scout browses platforms like LinkedIn, Wellfound, and Greenhouse. It searches for specific roles (like "AI Intern") and reads the results. Its only job is to filter out the noise—ignoring senior roles, irrelevant locations, or old postings, and building a clean list of fresh leads.

### 2. 🏗️ The Architect (The Evaluator)
The Architect takes the leads found by the Scout and reads the full Job Description. It then compares the job requirements directly against your CV. 
* *Does this job require PyTorch? Do you have PyTorch on your resume?* 
The Architect scores the job out of 10. If the score is too low, it skips it. If it's a match, it decides whether to auto-apply on the website or send a cold email.

### 3. ✍️ The Ghostwriter (The Communicator)
If the Architect decides a cold email is the best approach, the Ghostwriter takes over. It writes a short, punchy, highly personalized email to the hiring manager. It doesn't use generic fluff; it specifically mentions *your* past projects that solve the problems listed in *their* job description.

### 4. 🚀 The Dispatcher (The Executor)
The Dispatcher actually gets things done. It takes control of a web browser (using Playwright) to automatically fill out application forms, upload your resume, and answer questions. If it's sending an email, it finds the hiring manager's address, verifies it's real, and saves the email securely in your Gmail Drafts folder for you to review.

---

## 🖥️ The Command Center

You don't need to stare at a terminal window. Career-Orbit comes with a beautiful, real-time dashboard built in Next.js. 

From the dashboard, you can:
* **Start and Stop the Agents:** Safely launch or kill the AI team with a click.
* **Watch Them Work:** A live feed shows you exactly what the agents are thinking, which jobs they are reading, and what actions they are taking.
* **Track Your Funnel:** View analytics on how many jobs were found, how many were skipped, and how many successful applications or drafts were generated.

---

## ⚙️ Installation & Setup

### 1. What You Need
- **Python 3.10+**
- **Node.js 18+**
- A free **Groq API Key** (for lightning-fast AI processing).
- **Google OAuth2 Credentials** (so the agent can safely create drafts in your Gmail).

### 2. Getting Started
```bash
# Clone the repository
git clone https://github.com/Karanpr-18/Career-Orbit.git
cd Career-Orbit

# Setup the Python AI Backend
python -m venv venv
source venv/bin/activate  # (Use `venv\Scripts\activate` on Windows)
pip install -r requirements.txt
playwright install chromium

# Setup the Dashboard
npm install
npm run dev
```

### 3. Configure Your Profile
Create a `.env` file in the root folder with your keys. Then, ensure you have a `RESUME.md` or `CV.md` file in the folder. The AI will read this Markdown file to perfectly understand your skills and projects.

---

## 🚧 Open Challenges & Technical Limitations

Building a fully autonomous AI agent that interacts with the real web is incredibly difficult. Here are the engineering challenges the project currently faces, which we welcome the open-source community to help solve:

- **Bypassing Bot Protection:** Modern job portals (like Greenhouse and Lever) use aggressive anti-bot software like Cloudflare. Our browser automation sometimes gets blocked. Integrating advanced "stealth" browser techniques is an ongoing battle.
- **100% Free Search:** We currently rely on the `Serper.dev` API to search Google because free alternatives (like DuckDuckGo scraping) aggressively IP-ban automated agents. Finding a stable, totally free search architecture is a top priority.
- **Data Concurrency:** The dashboard and the AI backend currently share data via a simple `tracker.csv` file. This can cause read/write locks. Migrating to a robust local SQLite database is the next architectural step.
- **Email Verification Limits:** We use a commercial API (Emailable) to verify hiring managers' emails so your account doesn't get flagged for spam. Building a reliable, free local verifier (pinging SMTP servers directly) is complex but highly desired.

---

## 🤝 Contributing

We want to make job hunting completely effortless for everyone. If you can help solve any of the challenges above, we'd love your contributions! 

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

<div align="center">
  <i>Leveling the global job market through open-source intelligence.</i>
</div>