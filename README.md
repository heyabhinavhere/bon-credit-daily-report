# BON Credit Daily Amplitude Report

Automated agent that runs every morning, pulls the previous day's data from Amplitude, analyzes it with Claude, and emails a full report to the founders.

**What the email includes:**
- New signups count + DAU + cards linked + banks linked
- Per-user breakdown table for every new signup (screens visited, time spent, card/bank status)
- Claude's executive summary, key highlights, and watch list

---

## Setup (30–45 minutes total)

### Step 1 — Get your API keys

You need four credentials:

**Amplitude**
1. Go to [amplitude.com](https://amplitude.com) → Settings → Projects → select your project → General
2. Copy **API Key** and **Secret Key**

**Anthropic (Claude)**
1. Go to [console.anthropic.com](https://console.anthropic.com) → API Keys
2. Create a new key and copy it

**SendGrid**
1. Go to [app.sendgrid.com](https://app.sendgrid.com) → Settings → API Keys
2. Create API Key → Full Access → copy it
3. Go to Settings → Sender Authentication → verify the email address you'll send FROM (e.g. `reports@boncredit.com`)

---

### Step 2 — Find your Amplitude event names

The report tracks four specific events. You need to know exactly what they're called in your Amplitude account.

1. Go to amplitude.com → Data → Events
2. Find the event for: new user signup, card linked, bank account linked, screen/page view
3. Note the exact names (case-sensitive)

These go into your `.env` as `SIGNUP_EVENT`, `CARD_LINKED_EVENT`, `BANK_LINKED_EVENT`, `SCREEN_EVENT`.

> **Common names:** `Sign Up Complete`, `Registration Complete`, `Card Added`, `Bank Linked`, `Screen Viewed`, `Page View`

---

### Step 3 — Test locally first

```bash
# Clone or download this folder, then:
cd bon-credit-daily-report

# Install dependencies
pip install -r requirements.txt

# Copy .env.example and fill in your values
cp .env.example .env
# Edit .env with your real keys and event names

# Load the env and run for a specific date (safer than yesterday for first test)
export $(cat .env | xargs)
python main.py --date 2025-03-15

# If that works, test for yesterday
python main.py
```

You should see the script print progress and confirm email delivery. Check your inbox.

---

### Step 4 — Deploy to Railway

1. Go to [railway.app](https://railway.app) and create a free account
2. Click **New Project → Deploy from GitHub repo**
   - Push this folder to a GitHub repo first, then connect it
   - Or use **New Project → Empty Project → Add Service → GitHub Repo**
3. Once deployed, go to your service → **Variables** tab
4. Add every variable from `.env.example` with your real values
5. Set up the cron schedule:
   - Service → **Settings** → **Cron Schedule**
   - Expression: `0 16 * * *` (8:00 AM PST / 16:00 UTC)
   - Command: `python main.py`
   - In summer (PDT), change to `0 15 * * *` to stay at 8 AM local time

Railway's free tier gives you 500 execution hours/month. This script runs in under 2 minutes daily, so you'll use ~1 hour/month total. Well within free limits.

---

### Step 5 — Verify it's working

After the first scheduled run:
- Check your inbox at 8 AM PST
- Check Railway logs (Service → Deployments → latest run → View Logs) if something goes wrong

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Export API not available` | Your Amplitude plan may not include the Export API. Upgrade to Growth/Enterprise, or contact Amplitude support. |
| `No events found` | Double-check your API key/secret. Also check if the date had traffic in Amplitude's dashboard. |
| `Email not delivered` | Verify your sender email in SendGrid. Check spam folder. Review SendGrid activity feed. |
| `Wrong event counts` | Your event names in `.env` don't match Amplitude exactly. Go to Data → Events and copy the exact name. |
| `Screens showing as blank` | Update `SCREEN_EVENT` and `SCREEN_PROPERTY` in `.env` to match your app's tracking setup. |

---

## Backfilling past dates

```bash
python main.py --date 2025-03-01
```

Run this for any date you want to retroactively generate a report for.

---

## File overview

| File | What it does |
|---|---|
| `main.py` | Entry point, orchestrates the pipeline |
| `amplitude_client.py` | Calls Amplitude Export API, processes raw events into structured data |
| `claude_analyzer.py` | Sends data to Claude API, returns executive summary + highlights |
| `email_sender.py` | Builds the HTML email and sends via SendGrid |
| `requirements.txt` | Python dependencies |
| `railway.toml` | Railway deployment config |
| `.env.example` | Template for all required environment variables |
