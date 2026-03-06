# The Dividend Laggard System — v2.6
## Deployment Guide: GitHub + Streamlit Community Cloud

Everything runs free. No servers, no credit cards, no expiry.

---

## What you're setting up

```
GitHub repo (public)
├── signal_engine.py     ← runs daily at 2:55 PM EST
├── audit.py             ← runs monthly, fills forward returns
├── app.py               ← Streamlit dashboard
├── signal_output.json   ← written by engine, read by dashboard
├── deployment_log.json  ← running trade log
└── .github/workflows/   ← GitHub Actions automation
```

Streamlit Community Cloud watches your repo and serves the dashboard
at a public URL like: `https://dividend-laggard.streamlit.app`

---

## Step 1 — Create a GitHub account (if needed)

Go to https://github.com and sign up. Free.

---

## Step 2 — Create a new public repository

1. Click **+** → **New repository**
2. Name it: `dividend-laggard` (or anything you like)
3. Set to **Public**
4. Do NOT initialise with README (you'll push the files yourself)
5. Click **Create repository**

---

## Step 3 — Upload these files to GitHub

**Option A — GitHub web interface (easiest):**

1. In your new repo, click **Add file → Upload files**
2. Upload all files from this folder, preserving the folder structure:
   ```
   signal_engine.py
   audit.py
   app.py
   requirements.txt
   signal_output.json
   deployment_log.json
   .github/workflows/run_signal.yml
   ```
3. For the `.github/workflows/` folder: create the folder path manually
   using **Add file → Create new file**, type `.github/workflows/run_signal.yml`
   in the filename box, then paste the contents.

**Option B — Git command line:**

```bash
cd /path/to/this/folder
git init
git remote add origin https://github.com/YOUR_USERNAME/dividend-laggard.git
git add .
git commit -m "Initial commit — Dividend Laggard System v2.6"
git branch -M main
git push -u origin main
```

---

## Step 4 — Verify GitHub Actions is enabled

1. Go to your repo on GitHub
2. Click the **Actions** tab
3. If prompted, click **I understand my workflows, go ahead and enable them**
4. You should see **Dividend Laggard Signal Engine** listed

**Test it immediately:**
- Click **Dividend Laggard Signal Engine** → **Run workflow** → **Run workflow**
- Watch the logs — the full run takes 3–5 minutes
- After it finishes, `signal_output.json` in your repo will have today's data

**Scheduling note:**
The workflow runs at both 18:55 UTC and 19:55 UTC to cover daylight saving time.
Only one will be "correct" on any given day — the other just runs redundantly
(the engine is idempotent, so a double-run is harmless).

---

## Step 5 — Connect Streamlit Community Cloud

1. Go to https://share.streamlit.io
2. Sign in with your GitHub account
3. Click **New app**
4. Fill in:
   - **Repository:** `YOUR_USERNAME/dividend-laggard`
   - **Branch:** `main`
   - **Main file path:** `app.py`
5. Click **Deploy**

Your dashboard will be live at:
`https://YOUR_USERNAME-dividend-laggard-app-XXXXX.streamlit.app`

You can customise the URL in the Streamlit dashboard settings.
Share this link with anyone — no login required.

---

## Step 6 — Manual S5TH / NYMO override (if Yahoo throttles)

If the signal engine logs show S5TH failed, trigger a manual run with overrides:

1. Go to **Actions → Dividend Laggard Signal Engine → Run workflow**
2. Enter the S5TH value from TradingView in the **s5th_override** field
3. Optionally enter NYMO in the **nymo_override** field
4. Click **Run workflow**

The ETF matrix (Steps 0.5–3) always runs regardless — so even with a manual
S5TH override, the full deployment verdict is generated correctly.

---

## Monthly Audit

The audit runs automatically on the 1st–3rd calendar day of each month
(whichever falls on a weekday). It:
- Fetches 1M and 3M forward returns for all past deployments
- Calculates win rates and average returns by pass type
- Saves results to `audit_report.json`
- The Streamlit dashboard displays the report in the Monthly Audit section

To run it manually at any time:
```bash
python audit.py
```

---

## Resetting a streak counter manually

```bash
# ETF streak
python reset_streak.py HUTL.TO

# Manager streak (edit deployment_log.json directly)
# Set "manager_streaks": {"Hamilton": {"streak": 0}}
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| GitHub Actions not triggering | Check Actions tab is enabled. Verify cron syntax with crontab.guru |
| S5TH returns N/A | Use manual override in workflow_dispatch |
| Streamlit shows stale data | Hard refresh (Ctrl+Shift+R). Data updates when GitHub Actions pushes new JSON |
| yfinance rate limit errors | Re-run manually 30min later. Add `--s5th` override if needed |
| USD tickers not found | Verify `HYLD-U.TO` format in yfinance with: `yf.Ticker("HYLD-U.TO").info` |
| Dashboard CSS looks broken | Clear browser cache. Streamlit sometimes caches old CSS |
