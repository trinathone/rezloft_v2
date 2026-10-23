# Changelog

All notable changes to DiceBot. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **`run_linux.sh`.** One-command launcher for Linux desktops and servers, run
  after `setup.py`. Creates `.venv` and installs dependencies if missing, keeps
  the machine awake via `systemd-inhibit`, runs under a virtual display
  (`xvfb-run`) when there's no screen, and restarts the bot if it crashes.
  Arguments like `--dry-run` are passed through.

## [2.0.0]

v2 focuses on not lying about outcomes: an application is only logged as
`applied` when a submit is actually confirmed, and anything the bot can't handle
confidently is flagged for review instead of guessed at.

### Added

- **Screening-question handling.** Radio buttons, dropdowns, text inputs, and
  checkboxes are matched against `SCREENING_ANSWERS` in `config.py` and filled
  in. Unrecognized *required* questions are never guessed — the application is
  logged as `needs_review` with the question text, so you can add the answer and
  rerun.
- **Resume uploads.** Attaches `RESUME_PATH` when a form asks for a file
  directly, including when the real `<input type="file">` is hidden behind a
  styled button. Refuses to submit if no valid resume is configured.
- **Telegram reporting.** Optional status digest every 6 hours, an end-of-day
  summary, and immediate alerts for fatal errors. Configure via `setup.py` or
  `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`.
- **`--dry-run` mode.** Runs login, search, and Apply-button discovery without
  ever submitting. Also settable with `DRY_RUN=true`.
- **Multi-account isolation.** `INSTANCE=<name>` namespaces the browser profile,
  applications CSV, and log file per copy, so several accounts can run on one
  machine without fighting over the Chromium profile lock. Doubles as the
  Telegram message prefix.
- **Page-state detection.** Errors and status reports now say which kind of page
  the bot was on (`login`, `signup_wall`, `job_search`, `job_detail`, `blocked`).
- **Company and location** in `applications.csv`, read from the job page's
  schema.org `JobPosting` JSON-LD rather than guessed CSS selectors.
- **Sleep-window jitter** (`SLEEP_JITTER_MINUTES`) so the nightly pause isn't at
  the same clock time every day.
- **Tests** (`test_utils.py`) covering the CSV tracker, answer matching, instance
  isolation, and resume-path resolution — no browser or Dice account required.
- **CI** running the test suite and import checks on Python 3.11 and 3.12.
- **`LICENSE`** — the GPL-3.0 text the README had always claimed but never
  shipped, plus `SECURITY.md`.

### Fixed

- **Submits are now verified.** Previously, clicking Submit was assumed to work
  and logged as `applied`. A validation error meant a form that never submitted
  was still recorded as a successful application. The bot now waits for the
  submit button to disappear and logs `stuck` if it doesn't.
- **Bad credentials no longer retry forever.** A failed login was swallowed as a
  generic session error and retried roughly every 10 seconds indefinitely, which
  risked locking the account. Explicit bad-password and lockout messages now stop
  the bot immediately via `AuthenticationError`.
- **Browser process leak on partial startup.** Context creation and page setup
  sat outside the `try/finally`, so a crash mid-setup left an orphaned Chromium
  process holding the profile lock — which then broke every subsequent launch for
  an unrelated-looking reason.
- **Signup-wall recovery.** A dropped session that landed on a signup page
  instead of the login form would stall; the bot now re-navigates and retries
  credentials up to 3 times before falling back to the manual-login wait.
- **`JOB_TYPES` with both values.** `['contract', 'fulltime']` silently applied
  only the contract filter because of an `if`/`elif`.
- **Job-link selector fallback.** Job collection depended on a single
  `data-testid`; it now tries a chain so one markup change doesn't stop the run.
- **Python version mismatch.** README and CONTRIBUTING advertised 3.10+ while
  `setup.py` hard-exits below 3.11.

### Known limitations

- Dice.com only; Easy Apply only (external ATS redirects are logged as `stuck`).
- `_login()` still uses single selectors for the email/password fields with no
  fallback chain.
- `_detect_block()`'s CAPTCHA selectors have not been verified against a real
  live CAPTCHA.
- Automated applications violate Dice's Terms of Service. Use at your own risk.

## [1.0.0]

Initial release — keyword-driven Dice.com Easy Apply automation with CSV
deduplication, batch pacing, a nightly sleep window, anti-detection measures
(Bezier mouse movement, human-speed typing, randomized viewport and user agent),
and an interactive `setup.py` wizard.
