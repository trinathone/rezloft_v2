# Contributing to DiceBot

Thanks for your interest in contributing! DiceBot runs completely open-source under GPL v3 — every improvement you ship helps thousands of IT contractors on the bench.

---

## Quick Links

- 🐛 [Report a Bug](.github/ISSUE_TEMPLATE/bug_report.md)
- 💡 [Request a Feature](.github/ISSUE_TEMPLATE/feature_request.md)
- 💬 [Community Telegram](https://t.me/+rz7W7lhhUEkwOTM1)

---

## Before You Start

1. **Check existing issues** — someone may already be working on it.
2. **Open an issue first** for any non-trivial change. Discuss the approach before writing code.
3. **One PR per feature/fix** — keep changes focused and easy to review.

---

## Good First Issues

These are well-scoped tasks that don't require deep knowledge of the codebase:

| Issue | Description |
|---|---|
| Windows `.bat` installer | One-click `install.bat` that creates the venv, installs deps, and runs `setup.py`. |
| Login selector fallback | `_login()` in `dice_bot.py` uses single CSS selectors for the email/password fields with no fallback chain, unlike the job-search selectors which already have one (`JOB_LINK_SELECTORS`). Add the same pattern so a Dice login-page redesign doesn't break auth. |
| Verify CAPTCHA selectors live | `_detect_block()`'s CAPTCHA selectors have never been confirmed against a real Dice CAPTCHA. If you hit one, capture the DOM and update the selector list. |
| File upload support | The screening-question handler (`_get_unanswered_questions`) doesn't scan `input[type="file"]` at all, so an application requiring a fresh resume/cover-letter upload silently ends up `stuck` instead of completing. |

---

## Development Setup

```bash
git clone https://github.com/trinathone/rezloft_v2.git
cd rezloft_v2
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Configure credentials
cp env.example .env
# Edit .env with your Dice credentials

# Run in DEBUG mode (verbose logging)
DEBUG=true python3 dice_bot.py
```

---

## Project Layout

```
rezloft_v2/
├── dice_bot.py          # Main bot — Playwright browser automation
├── config.py            # All tunable settings, including SCREENING_ANSWERS
├── utils.py             # Helpers: logging, mouse movement, form filling, CSV tracker, Telegram
├── setup.py             # Interactive setup wizard
├── test_utils.py        # Unit tests for the pure logic in utils.py
├── keywords.txt         # Your keyword list (git-ignored)
├── keywords.example.txt # Starter keywords
├── requirements.txt
└── applications.csv     # Auto-generated run log (git-ignored)
```

---

## Code Style

- **Python 3.10+**
- Follow existing patterns — async/await throughout, `logger` from `utils.py` for all output
- Keep anti-detection logic in `utils.py`
- No new dependencies without a good reason — the install is already heavier than ideal

---

## Pull Request Checklist

- [ ] Tested locally against a real Dice account (or dry-run mode)
- [ ] No credentials or personal data in the diff
- [ ] `DEBUG=true` output is clean (no noisy new log lines)
- [ ] Updated `README.md` if you changed configuration options
- [ ] PR description explains *what* and *why*

---

## Platform Expansion (Larger PRs)

The highest-value contributions are additional platform scrapers:

- **Indeed Easy Apply** — same Playwright approach, different selectors
- **ZipRecruiter Easy Apply** — similar structure
- **LinkedIn Easy Apply** — harder (rate limiting + anti-bot), discuss in issue first

For a new platform, create `<platform>_bot.py` mirroring `dice_bot.py`, a matching `<platform>_config.py`, and update the README.

---

## License

By contributing, you agree your code is released under [GPL v3](LICENSE).
