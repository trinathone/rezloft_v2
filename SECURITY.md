# Security Policy

## Reporting a Vulnerability

Email **trinath.connect@proton.me** with the details. Please don't open a public
issue for anything that exposes credentials or user data.

Include what you can: the affected file, how to reproduce it, and what an
attacker would gain. Expect a reply within a few days.

## What This Tool Handles

DiceBot stores and uses real credentials, so a few things are worth knowing
before you run it.

### Your Dice password is stored in plaintext

`.env` is a plaintext file. Anyone with read access to the project folder — or
to a backup of it — can read your Dice login. The bot needs the password to log
in and has no way around that.

- `.env` is in `.gitignore`. Keep it that way; never commit it.
- Don't paste your `.env` contents into issues, pull requests, chat logs, or AI
  assistants. If you already have, change your Dice password.
- On a shared or remote machine, restrict it: `chmod 600 .env`

### The browser profile is a live session

`browser_data/` holds the logged-in Chromium profile, including session cookies.
Copying that folder is equivalent to handing over an authenticated session — it
does not require your password to reuse. It's gitignored for the same reason
`.env` is.

### Files that must never be committed

Already covered by `.gitignore`, listed here so you know what to check:

| Path | Why |
|---|---|
| `.env`, `.env.*` | Dice password, Telegram bot token |
| `browser_data*/` | Live authenticated session cookies |
| `applications*.csv` | Your application history |
| `*.log` | May contain job URLs and run details |

Before pushing, `git status` should never show any of these.

### Telegram tokens

A leaked bot token lets someone else post to your chat. Revoke it with
`/revoke` via [@BotFather](https://t.me/BotFather) and set the new one in `.env`.

## Scope

This project automates a logged-in session on **your own** Dice account. Doing so
violates Dice's Terms of Service (see the README) — that's an accepted, disclosed
risk of using it, not a vulnerability report. Reports about defeating Dice's
anti-bot measures are out of scope.

In scope: anything that leaks credentials, writes secrets somewhere unexpected,
executes untrusted input, or submits data on your behalf that you did not
configure.
