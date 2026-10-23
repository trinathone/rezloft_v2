#!/usr/bin/env bash
# Runs DiceBot on Linux (desktop or headless server).
# Run this after `python3 setup.py`.
#
# Usage:
#   ./run_linux.sh              # run for real
#   ./run_linux.sh --dry-run    # any args are passed straight to dice_bot.py
#
# What it does:
#   - creates .venv and installs dependencies if they're missing
#   - stops if setup.py hasn't been run yet (no .env)
#   - keeps the machine from sleeping (systemd-inhibit), like caffeinate on Mac
#   - uses a virtual display (xvfb-run) on servers with no screen
#   - restarts the bot if Python crashes, with a growing wait between tries

set -uo pipefail

cd "$(dirname "$0")"

VENV_DIR=".venv"
MAX_RESTART_WAIT=300   # seconds

log() { echo "[run_linux] $*"; }

# ── 1. Python + virtual environment ─────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    log "python3 not found. Install it first, e.g.:"
    log "  sudo apt install -y python3 python3-venv python3-pip"
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    log "Python 3.11+ is required (found $(python3 --version 2>&1))."
    exit 1
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    log "No virtual environment found — creating $VENV_DIR ..."
    if ! python3 -m venv "$VENV_DIR"; then
        log "Could not create venv. On Debian/Ubuntu run: sudo apt install -y python3-venv"
        exit 1
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    log "Installing dependencies (takes a few minutes the first time) ..."
    pip install --upgrade pip >/dev/null
    pip install -r requirements.txt || { log "pip install failed."; exit 1; }
    # --with-deps installs Chromium's system libraries; needs sudo.
    if ! playwright install --with-deps chromium; then
        log "Installing Chromium with system deps failed — trying without them ..."
        playwright install chromium || { log "playwright install failed."; exit 1; }
    fi
else
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi

# ── 2. Setup must be done ───────────────────────────────────────
if [ ! -f ".env" ]; then
    log "No .env found. Run the setup wizard first:"
    log "  source $VENV_DIR/bin/activate && python3 setup.py"
    exit 1
fi

# ── 3. Build the launch command ─────────────────────────────────
CMD=(python3 dice_bot.py "$@")

# No screen (SSH / server)? Use a virtual one so the visible browser still works.
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    if command -v xvfb-run >/dev/null 2>&1; then
        log "No display detected — using a virtual display (xvfb-run)."
        CMD=(xvfb-run -a --server-args="-screen 0 1920x1080x24" "${CMD[@]}")
    else
        log "WARNING: no display and xvfb-run isn't installed."
        log "  Either: sudo apt install -y xvfb"
        log "  Or set HEADLESS = True in config.py"
    fi
fi

# Keep the machine awake while the bot runs. Only if systemd-inhibit actually
# works here (it fails in containers / minimal servers with no system bus).
if command -v systemd-inhibit >/dev/null 2>&1 \
   && systemd-inhibit --what=idle --who=DiceBot --why=check true >/dev/null 2>&1; then
    CMD=(systemd-inhibit --what=sleep:idle --who=DiceBot \
         --why="Applying to jobs" --mode=block "${CMD[@]}")
fi

# ── 4. Run, restarting on crashes ───────────────────────────────
STOP=0
trap 'STOP=1; log "Stopping..."' INT TERM

log "Starting DiceBot. Press Ctrl+C to stop."
attempt=0
while true; do
    "${CMD[@]}"
    code=$?

    if [ "$STOP" -eq 1 ]; then
        break
    fi

    # Exit 0 = the bot stopped on purpose (e.g. wrong password) — don't loop.
    if [ "$code" -eq 0 ]; then
        log "Bot exited normally. Check dice_bot*.log for details."
        break
    fi

    attempt=$((attempt + 1))
    wait=$((30 * attempt))
    [ "$wait" -gt "$MAX_RESTART_WAIT" ] && wait=$MAX_RESTART_WAIT
    log "Bot crashed (exit $code). Restarting in ${wait}s (attempt #$attempt) ..."
    sleep "$wait" &
    wait $! 2>/dev/null
    [ "$STOP" -eq 1 ] && break
done

log "Done."
