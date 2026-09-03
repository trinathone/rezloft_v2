<div align="center">

<h1>🎲 DiceBot</h1>

<p><strong>Apply to 300 Dice.com jobs per day — automatically, while you sleep.</strong></p>

<img src="https://img.shields.io/badge/version-2.0-2dd4bf?style=flat-square&labelColor=0d1117"/>
<img src="https://img.shields.io/github/stars/trinathone/rezloft?style=flat-square&color=2dd4bf&labelColor=0d1117"/>
<img src="https://img.shields.io/badge/license-GPL--v3-2dd4bf?style=flat-square&labelColor=0d1117"/>
<img src="https://img.shields.io/badge/platform-Python%203.10%2B-2dd4bf?style=flat-square&labelColor=0d1117"/>
<img src="https://img.shields.io/badge/CAPTCHAs_triggered-0-2dd4bf?style=flat-square&labelColor=0d1117"/>

<br/><br/>

> **8,202 applications submitted in 10 days. 99.76% success rate. Zero bans.**

</div>

---

## What It Does

DiceBot logs into your Dice.com account, cycles through keywords you control, and clicks **Easy Apply** on every matching job — fully automated. It tracks every application in a CSV so it never applies to the same job twice, then puts itself to sleep at 2 AM and wakes back up at 3 AM without you touching a thing.

**Who it's for:**
- C2C contractors on the bench who need mass vendor visibility fast
- Bench sales recruiters managing candidate pipelines on Dice
- Independent IT consultants who want inbound vendor calls, not cold outreach

---

## Results (Real Run: April 14–23, 2026)

| Metric | Value |
|---|---|
| Total applications submitted | **8,202** |
| Success rate | **99.76%** |
| Failed applications | 10 |
| Bot detections / CAPTCHAs | **0** |
| Average per day | ~250–300 |
| Run duration | 10 days, unattended |

> ⚠️ **Stay under 300 apps/day.** The bot enforces this by default via `BATCH_SIZE` and `BATCH_BREAK_MINUTES` in `config.py`.

---

## Quick Start

> **First time? Read [START_HERE.md](START_HERE.md) for Windows + macOS step-by-step walkthrough.**

```bash
# 1. Clone and install (≈ 2 min)
git clone https://github.com/trinathone/rezloft.git
cd rezloft
python3 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 2. Setup wizard — sets your Dice credentials + keywords + speed
python3 setup.py

# 3. Run
python3 dice_bot.py
```

The bot opens a browser, logs in, and starts applying. Applications are logged to `applications.csv` in real time.

---

## Configuration

### `keywords.txt` — what to search

One keyword per line. The bot cycles them in order, moving to the next when the current keyword is exhausted.

```
# keywords.txt
Python Developer
AWS Solutions Architect
Data Engineer
DevOps Engineer
Java Developer
```

Copy `keywords.example.txt` as your starting point — 20 common IT/C2C terms included.

### `.env` — credentials

Created automatically by `python3 setup.py`. You can also edit it manually:

| Variable | Required | Description |
|---|---|---|
| `DICE_EMAIL` | ✅ | Your Dice.com login email |
| `DICE_PASSWORD` | ✅ | Your Dice.com password |
| `PROXY` | ❌ | Optional SOCKS5/HTTP proxy |
| `DEBUG` | ❌ | `true` for verbose logging |
| `DRY_RUN` | ❌ | `true` to locate Apply buttons without submitting (or pass `--dry-run`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | ❌ | Enables the status digest below (set via `setup.py` or manually) |

### Telegram Status Digest

If both Telegram values are set, the bot sends a status message every 6 hours (`config.TELEGRAM_REPORT_HOURS`): applications today vs. your daily target, needs-review/failed/skipped counts, how many times it's been blocked and restarted, and the current page it's on. Fatal errors (bad credentials, 10 consecutive crashes) send an immediate message instead of waiting for the next digest. Leave the token/chat ID blank to disable entirely — every notification call is a no-op without both set.

### `config.py` — `SCREENING_ANSWERS`

Some Easy Apply forms ask a question before letting you submit (work authorization, sponsorship, desired salary, years of experience). The bot matches each key below against the question text and fills in the value — radio/dropdown answers match by substring, text answers are typed as-is:

```python
SCREENING_ANSWERS = {
    "authorized to work":  "Yes",
    "require sponsorship": "No",
    "years of experience": "5",
    "desired salary":      "120000",
}
```

If a required question doesn't match anything here, the bot does **not** guess — it logs the application as `needs_review` in `applications.csv` instead of `applied`, so you never end up submitting a wrong answer on autopilot. Add the missing keyword and rerun; it'll retry automatically since `needs_review` rows aren't treated as applied.

### `config.py` — speed & filters

| Setting | Default | Description |
|---|---|---|
| `EASY_APPLY_ONLY` | `True` | Only Easy Apply jobs |
| `JOB_TYPES` | `['fulltime']` | `'contract'` or `'fulltime'` |
| `REMOTE_ONLY` | `False` | Remote jobs only |
| `BATCH_SIZE` | `(80, 100)` | Apps per batch before a break |
| `BATCH_BREAK_MINUTES` | `(2, 3)` | Break length between batches |
| `SLEEP_HOUR_START` | `2` | Bot sleeps after this hour |
| `SLEEP_HOUR_END` | `3` | Bot wakes at this hour |
| `HEADLESS` | `False` | Set `True` for server deploys |

---

## Run 24/7 for Free (Oracle Cloud)

[Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) gives you a permanently free ARM VM (4 OCPUs, 24 GB RAM). No credit card tricks — it's actually free.

```bash
# On your Oracle Ubuntu VM
sudo apt update && sudo apt install -y python3-pip python3-venv
git clone https://github.com/trinathone/rezloft.git && cd rezloft
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium --with-deps

python3 setup.py        # configure once
# set HEADLESS = True in config.py
screen -S dicebot
python3 dice_bot.py
# Ctrl+A D to detach — bot keeps running
```

---

## How It Works

```
keywords.txt
    │
    ▼
Dice.com Search (Playwright + Chromium)
    │  per-keyword, paginated
    ▼
Easy Apply filter → parse job listings
    │  skip if URL already in applications.csv
    ▼
Multi-step form walk + Submit
    │
    ▼
applications.csv  ← timestamp, title, URL, status
    │
    ▼
Batch break → next keyword → sleep 2–3 AM → repeat
```

Anti-detection: Bezier mouse curves, human-speed typing, randomized viewport + user-agent, randomized delays, no screenshots, rotating logs.

---

## Known Limitations

- **Dice.com only.** No LinkedIn, Indeed, ZipRecruiter — yet. (See Contributing.)
- **Easy Apply only.** External ATS (Workday, Greenhouse, Lever) are skipped.
- **Terms of Service.** Automated applications violate Dice's ToS. Use at your own risk.
- Company/location are scraped best-effort from the job detail page — if Dice changes that page's markup the fields may go blank again, but the application still gets submitted.
- Screening-question matching (`SCREENING_ANSWERS`) works by matching question text — highly custom or JS-rendered questions may not be recognized. Unrecognized required questions are logged as `needs_review`, never guessed.

---

## Contributing

PRs welcome. Check [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

**High-impact areas — good first issues:**

| Label | Task |
|---|---|
| `good first issue` | Windows one-click `.bat` installer |
| `good first issue` | Telegram notification on batch completion |
| `enhancement` | Indeed Easy Apply support |
| `enhancement` | ZipRecruiter Easy Apply support |
| `enhancement` | Web dashboard over `applications.csv` |
| `enhancement` | CAPTCHA solver integration |

Open an issue before starting any large feature.

---

## Community & Support

- 💬 **Telegram:** https://t.me/+rz7W7lhhUEkwOTM1
- 🌐 **Web:** https://rezloft.vercel.app/
- 📧 **Email:** trinath.connect@proton.me
- ⭐ **If DiceBot helped you land a contract, star the repo** — it helps others find it.

---

## License

GPL v3 — Free to use and modify. If you build a paid product on top of this, you must open-source it too.
