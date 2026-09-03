#!/bin/bash
# Keeps Mac awake and runs the bot forever
# Usage: ./run.sh

cd "$(dirname "$0")"
source .venv/bin/activate

echo "Starting Dice Bot with caffeinate (Mac won't sleep)..."
echo "Press Ctrl+C to stop."
echo ""

# caffeinate -i keeps Mac awake. Wrapping python with it.
caffeinate -i python dice_bot.py
