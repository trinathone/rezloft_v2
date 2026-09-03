"""
Bot 1 Configuration — Full Time + Easy Apply, max throughput.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Credentials ──────────────────────────────────────────────
DICE_EMAIL    = os.getenv("DICE_EMAIL", "")
DICE_PASSWORD = os.getenv("DICE_PASSWORD", "")

# ── Search Keywords ───────────────────────────────────────────
KEYWORDS_FILE = Path(__file__).parent / "keywords.txt"


def load_keywords() -> list:
    """Load search keywords from keywords.txt in the project root."""
    if not KEYWORDS_FILE.exists():
        print(
            "ERROR: keywords.txt not found. Please create it with one keyword "
            "per line. See keywords.example.txt for reference."
        )
        sys.exit(1)

    keywords = []
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            keywords.append(line)

    if not keywords:
        print(
            "ERROR: keywords.txt is empty or contains only comments. "
            "Please add at least one keyword."
        )
        sys.exit(1)

    return keywords

# ── Only 2 Filters Applied ───────────────────────────────────
EASY_APPLY_ONLY = True
JOB_TYPES       = ['fulltime']
REMOTE_ONLY     = False
JOB_LOCATION    = ""             # no location filter — widest net

# ── Speed — tuned for ~60 apps/hour ─────────────────────────
MIN_DELAY             = 1
MAX_DELAY             = 3
PAGE_LOAD_WAIT        = (1, 2)
TYPING_SPEED          = (40, 100)
MAX_CONSECUTIVE_FAILS = 5
BREAK_EVERY_N_APPS    = 10
BREAK_DURATION        = (20, 40)
BATCH_SIZE            = (80, 100)
BATCH_BREAK_MINUTES   = (2, 3)

# ── Sleep Schedule ───────────────────────────────────────────
SLEEP_HOUR_START = 2   # 2am
SLEEP_HOUR_END   = 3   # 3am — only 1 hour break

# ── Browser ──────────────────────────────────────────────────
BROWSER_PROFILE_DIR = Path(__file__).parent / "browser_data"
HEADLESS            = False
PROXY               = os.getenv("PROXY", "")

# ── Logging ──────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "dice_bot.log"
CSV_LOG  = Path(__file__).parent / "applications.csv"
DEBUG    = os.getenv("DEBUG", "false").lower() == "true"

# ── Dry Run ──────────────────────────────────────────────────
# When true, the bot does everything up to clicking Apply, then logs
# "dry_run" and moves on instead of submitting. Set via .env or
# `python3 dice_bot.py --dry-run`.
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# ── Screening Question Answers ────────────────────────────────
# Easy Apply forms sometimes ask questions (work auth, salary, etc.)
# before letting you submit. The bot matches these keys against the
# question text (case-insensitive substring match) and fills in the
# value. Radio/dropdown answers must match one of the option labels
# (substring match); text answers are typed verbatim.
# Unmatched required questions are NOT guessed — the application is
# logged as "needs_review" instead of "applied" so you never submit
# a wrong answer on autopilot. Add more keys as you see what Dice asks.
SCREENING_ANSWERS = {
    "authorized to work":  "Yes",
    "require sponsorship": "No",
    "need sponsorship":    "No",
    "visa sponsorship":    "No",
    "years of experience": "5",
    "desired salary":      "120000",
    "expected salary":     "120000",
    "salary expectation":  "120000",
    "notice period":       "2 weeks",
    "willing to relocate": "Yes",
    # The standard "I certify the above is accurate" attestation on most job
    # apps — not a stand-in for consent checkboxes. Deliberately NOT matching
    # generic "I agree" text: that phrase also covers things like marketing
    # opt-in or background-check consent, which shouldn't be auto-approved.
    "i certify":           "Yes",
    "i acknowledge":       "Yes",
}

# ── Sleep Schedule Jitter ──────────────────────────────────────
# The sleep window shifts by a random +/- offset (minutes), picked once
# per run, so the bot isn't idle at the exact same clock time every day.
SLEEP_JITTER_MINUTES = 30

# ── Telegram Notifications (optional) ───────────────────────────
# Set via `python3 setup.py` or manually in .env. Leave blank to disable —
# every notification call is a no-op without both values set.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_REPORT_HOURS = 6   # how often the status digest is sent

# Optional label prefixed to every Telegram message — set this per instance
# (e.g. BOT_LABEL=Account2 in that copy's .env) if multiple isolated copies
# of this bot share the same Telegram chat, so messages stay distinguishable.
BOT_LABEL = os.getenv("BOT_LABEL", "")

# Rough daily application target, used only to estimate "how many more
# expected today" in the Telegram digest. Set by setup.py's speed preset.
DAILY_APPLICATION_TARGET = 250
