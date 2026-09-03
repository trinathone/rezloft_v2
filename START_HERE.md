# 👋 Start Here — Read This First

---

# 🪟 SETUP FOR WINDOWS

## Step 1 — Install Python (Windows)
Download Python 3.11+ from https://python.org/downloads

> ⚠️ During install — check **"Add Python to PATH"** before clicking Install Now

Verify it worked — open Command Prompt and run:
```
python --version
```
Should show `Python 3.11` or higher.

## Step 2 — Open Terminal in This Folder (Windows)
1. Open the project folder in File Explorer
2. Click the address bar at the top
3. Type `cmd` and press Enter
4. A Command Prompt opens inside the folder

## Step 3 — Install Dependencies (Windows)
```
python -m pip install -r requirements.txt
playwright install chromium
```
(Takes 2–3 minutes — Chromium is ~150MB)

## Step 4 — Run Setup Wizard (Windows)
```
python setup.py
```

This will ask you:
- Your Dice.com email and password
- Job type (contract / fulltime / both)
- Your keywords (we give you a ChatGPT prompt to generate them)
- Daily application speed (50–400/day)

Setup takes under 3 minutes and configures everything automatically.

## Step 5 — Run the Bot (Windows)
```
python dice_bot.py
```
⚠️ Keep the Command Prompt window open while the bot is running.

---

# 🍎 SETUP FOR MAC

## Step 1 — Install Python (Mac)
Download Python 3.11+ from https://python.org/downloads

After installing, open **Terminal** and verify:
```
python3 --version
```
Should show `Python 3.11` or higher.

> ⚠️ On Mac, always use `python3` and `pip3` — not `python` or `pip`

## Step 2 — Open Terminal in This Folder (Mac)
1. Open the project folder in Finder
2. Right-click inside the folder
3. Select **"New Terminal at Folder"**

Or drag the folder onto Terminal in your Dock.

## Step 3 — Create Virtual Environment (Mac)
```
python3 -m venv .venv
source .venv/bin/activate
```
You'll see `(.venv)` appear at the start of your terminal line — that means it's active.

> ⚠️ You must run `source .venv/bin/activate` every time you open a new terminal before running the bot.

## Step 4 — Install Dependencies (Mac)
```
pip3 install -r requirements.txt
playwright install chromium
```
(Takes 2–3 minutes — Chromium is ~150MB)

## Step 5 — Run Setup Wizard (Mac)
```
python3 setup.py
```

This will ask you:
- Your Dice.com email and password
- Job type (contract / fulltime / both)
- Your keywords (we give you a ChatGPT prompt to generate them)
- Daily application speed (50–400/day)

Setup takes under 3 minutes and configures everything automatically.

## Step 6 — Run the Bot (Mac)
```
python3 dice_bot.py
```
⚠️ Keep the Terminal window open while the bot is running.

---

# ❓ Having Issues?

Paste this into Claude.ai or ChatGPT:
```
"Help me set up this project: [YOUR GITHUB URL]"
```
The AI will guide you through any errors step by step.

## Need Help?
- Join Telegram community: https://t.me/+rz7W7lhhUEkwOTM1
- Email: trinath.connect@proton.me
