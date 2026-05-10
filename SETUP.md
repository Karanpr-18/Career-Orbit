# ⚙️ Setup & Configuration Guide

Follow these steps to get CareerOrbit up and running on your local machine.

## 1. Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Groq API Key**: Get it from [Groq Console](https://console.groq.com/).
- **Google Cloud Project**: For Gmail API (Cold Emailing).

## 2. Installation

### Clone the Repository
```bash
git clone https://github.com/your-username/CareerOrbit.git
cd CareerOrbit
```

### Setup Python Environment
```bash
# Create a virtual environment
python -m venv venv

# Activate it
source venv/bin/bin/activate  # Linux/Mac
# venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
```

### Setup Frontend
```bash
npm install
```

## 3. Environment Configuration

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_api_key_here
RESUME_PATH=/path/to/your/resume.pdf
MAX_APPLICATIONS_PER_DAY=50
```

## 4. Gmail API Setup (Crucial)

To enable automated cold email drafting:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **Gmail API**.
4. Go to **OAuth Consent Screen**:
   - Choose **External**.
   - Add your email as a **Test User**.
   - Add the scope: `https://www.googleapis.com/auth/gmail.compose`.
5. Go to **Credentials**:
   - Create **OAuth 2.0 Client ID** (Type: Desktop App).
   - Download the JSON file and rename it to `credentials.json`.
   - Place it in the root folder of this project.

### Generate the Token
Run this command once in your terminal to authenticate:
```bash
python -c "from tools import gmail_draft_email; gmail_draft_email('your-email@example.com', 'Auth', 'Auth')"
```
Follow the browser prompts to allow access. This will create `token.json`.

## 5. Running the Application

### Start the Dashboard
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### Start the Agent
You can start the agent directly from the dashboard's **Agent Command Center**. Alternatively, run it from the CLI:
```bash
python job_hunter.py --force
```

## 🛠️ Troubleshooting

- **Rate Limits**: If you hit Groq rate limits, the agent will log an error and skip the job. Consider upgrading your Groq tier or increasing the delay in `config.py`.
- **Form Filling**: If Playwright fails to find fields, it will fallback to cold emailing. You can adjust the selectors in `tools.py`.
