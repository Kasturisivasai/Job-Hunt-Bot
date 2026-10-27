# 🎯 Zero-Click Daily Cloud Job Pipeline

An automated, serverless, zero-maintenance job intelligence pipeline that runs in the cloud every morning, filters career feeds for visa eligibility and specific target roles, deduplicates against past postings, and delivers an actionable morning digest with **1-tap mobile apply links straight to your phone via Telegram**.

---

## 🌟 Key Architecture & Highlights

```
┌─────────────────────────────────────────────────────────────┐
│ GitHub Actions (Runs daily at 8:00 AM CST - 100% Free)      │
│                                                             │
│ 1. Fetches career feeds / public ATS APIs (Remotive/Jobicy) │
│ 2. Applies Hard Visa Exclusions & Target Role Keyword Regex │
│ 3. Deduplicates against past seen Job IDs (seen_jobs.json)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│ Persistent Deduplication Cache│ │ Telegram Bot Push to Phone│
│ - seen_jobs.json auto-commit  │ │ - Morning digest message  │
│ - Zero external database cost │ │ - Direct 1-tap apply link │
└───────────────────────────────┘ └───────────────────────────┘
```

- **Zero-Click & Zero-Maintenance:** Runs completely serverless on GitHub's cloud runners. Your laptop never needs to stay on or awake.
- **Fast (< 10 seconds):** Queries public ATS and aggregator feeds directly via REST, eliminating fragile headless browser automation (Selenium/Playwright) that triggers anti-bot Captchas.
- **Hard Visa Sponsorship Filter:** Regex engine instantly filters out postings containing disqualifiers such as `"will not sponsor"`, `"must be a US citizen"`, `"no visa sponsorship"`, or `"security clearance required"`.
- **Deduplication Engine:** Automatically maintains `seen_jobs.json` so you never get notified about the same job twice.
- **Mobile Workflow:** 1-tap `[👉 Tap to 1-Click Apply]` buttons open directly in your mobile browser.
- **Manual Trigger from Phone:** Trigger an immediate refresh anytime via the GitHub Mobile App (`Actions` → `Run workflow`).

---

## 📁 Project Structure

```
job_pipeline/
├── .github/
│   └── workflows/
│       └── daily_scrape.yml   # Daily 8:00 AM CST scheduled GitHub Action
├── config.py                  # Roles, exclusion regex, and feed configurations
├── pipeline.py                # Core orchestration script (fetch, filter, dedupe, push)
├── test_pipeline.py           # Unit tests (visa filters, role matching, cache, formatting)
├── requirements.txt           # Dependency info (100% Python standard library)
├── .env.example               # Template for Telegram Bot credentials
├── .gitignore                 # Standard Python & secret exclusion
└── README.md                  # This documentation
```

---

## 🚀 Quickstart & Local Testing

### 1. Run in Dry-Run Mode (No credentials required)
You can test the pipeline locally right now:

```bash
cd job_pipeline
python pipeline.py --dry-run
```

### 2. Run the Unit Test Suite
```bash
python test_pipeline.py
```

---

## 📱 Setting Up Your Mobile Telegram Bot (2 Minutes)

### Step 1: Create Your Bot
1. Open the **Telegram** app on your phone or desktop.
2. Search for `@BotFather` (verified bot with a blue checkmark) and tap **Start**.
3. Send the command:
   ```
   /newbot
   ```
4. Follow the prompts to name your bot (e.g. `MyJobHunterBot`) and choose a username (e.g. `MyJobHunter_bot`).
5. BotFather will provide an **HTTP API Token** (format: `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`). **Save this token.**

### Step 2: Get Your Personal Chat ID
1. Open your newly created bot in Telegram and press **Start** (or send any text message to it).
2. Search for `@userinfobot` in Telegram and press **Start**. It will immediately reply with your numerical **Id** (e.g. `987654321`).
3. *(Alternative without third-party bots)*: In any browser, open:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   Look for `"chat":{"id": 987654321}` in the returned JSON.

### Step 3: Configure Local `.env` and Verify
1. Create a `.env` file inside `job_pipeline/`:
   ```bash
   cp .env.example .env
   ```
2. Paste your credentials into `.env`:
   ```ini
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
   TELEGRAM_CHAT_ID=987654321
   ```
3. Test delivery to your phone immediately:
   ```bash
   python pipeline.py --test-telegram
   ```
   Your phone should immediately buzz with a test notification!

---

## ☁️ Automating on GitHub Actions (100% Free Daily Runs)

To have GitHub run this pipeline automatically every morning at 8:00 AM CST:

### 1. Push to GitHub
If this project is in a GitHub repository:
- Ensure the workflow file is located at `.github/workflows/daily_scrape.yml`.

### 2. Add Secrets to GitHub Repository
1. Navigate to your GitHub repository in your browser.
2. Go to **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret** and add:
   - `TELEGRAM_BOT_TOKEN`: Your bot token from `@BotFather`.
   - `TELEGRAM_CHAT_ID`: Your numerical chat ID.
   - *(Optional)* `TARGET_ROLES`: Custom comma-separated roles (e.g. `data scientist, machine learning engineer`).

### 3. Enable Workflow Permissions
Under **Settings** → **Actions** → **General** → **Workflow permissions**, select:
- **Read and write permissions** (allows the workflow to commit the updated `seen_jobs.json` deduplication cache).

---

## 📲 How to Trigger from Your Phone

1. Install the official **GitHub** app on iOS or Android.
2. Open your repository in the app.
3. Tap **Actions** → **Zero-Click Daily Job Pipeline**.
4. Tap **Run workflow**.
5. Within 15 seconds, the new job digest will hit your Telegram app with direct 1-tap apply links!

---

## ⚙️ Customization

### Adding / Editing Target Roles
Edit `DEFAULT_TARGET_ROLES` in [config.py](file:///c:/Users/ksska/OneDrive/Desktop/Ollama/Edit%20project/job_pipeline/config.py) or set the `TARGET_ROLES` environment variable:
```python
TARGET_ROLES = [
    "data scientist",
    "senior data analyst",
    "analytics engineer",
    "decision scientist",
    "machine learning engineer",
    "ai engineer",
]
```

### Adding Visa Exclusion Rules
Add any regex pattern to `EXCLUSION_PATTERNS` in [config.py](file:///c:/Users/ksska/OneDrive/Desktop/Ollama/Edit%20project/job_pipeline/config.py):
```python
EXCLUSION_PATTERNS = [
    r"will not sponsor",
    r"no visa sponsorship",
    r"without sponsorship",
    r"must be a us citizen or permanent resident",
    r"security clearance required",
    # Add custom filters here
]
```
