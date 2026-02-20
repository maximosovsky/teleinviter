# 🏗 Architecture — InviterLink Bot

## Overview

Serverless Telegram bot deployed on Vercel. Receives webhooks, builds timezone-aware meeting cards, schedules reminders via QStash, and sends personal DMs via Telethon userbot.

---

## Request Flow

```
User (Telegram)
    │
    ▼
Telegram API ──webhook POST──► Vercel (api/index.py)
                                    │
                              ┌─────┴──────┐
                              │ Flask app   │
                              │ + TeleBot   │
                              └─────┬──────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
          is_user_allowed?    parse message        /adduser
          (Redis → env)       (title, date,        /removeuser
               │               time, link,         /users
               │               @usernames)         (admin only)
               │                    │
               ▼                    ▼
        ┌──────────┐    ┌─────────────────────┐
        │ Upstash  │    │  Build meeting card  │
        │ Redis    │    │  + timezone convert  │
        │(allowlist)│    │  + Google Calendar   │
        └──────────┘    └─────────┬───────────┘
                                  │
                          ┌───────┴───────┐
                          │               │
                    QStash publish    bot.send_message
                    (2 reminders)    (card + buttons)
                          │
                    ┌─────┴─────┐
                    │           │
               delay 45min  delay 5min
                    │           │
                    ▼           ▼
              /reminder    /reminder
              (type=main)  (type=urgent)
                    │           │
               ┌────┴────┐  ┌──┴─────┐
               │ Bot msg │  │ Bot msg│
               │ + DMs   │  │ + DMs  │
               └─────────┘  └────────┘
```

---

## Project Structure

```
teleinv/
├── api/
│   └── index.py           # Main bot logic (Flask + TeleBot)
├── generate_session.py     # Telethon StringSession generator
├── logo.png                # Bot logo
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel routing config
├── README.md               # Documentation
├── ARCHITECTURE.md         # This file
├── llms.txt                # LLM-friendly summary
└── llms-full.txt           # LLM-friendly full context
```

---

## Components

### 1. Flask App (`api/index.py`)

Single-file serverless function. Routes:

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Health check page |
| `/` | POST | Telegram webhook receiver |
| `/reminder` | POST | QStash callback (fires reminders) |

### 2. TeleBot (pyTelegramBotAPI)

Handles Telegram messages and callbacks:

| Handler | Trigger | Action |
|---|---|---|
| `/start` | Command | Show format help |
| `/cancel` | Command | Cancel last reminder (in-memory) |
| `/adduser` | Command | Add user to Redis allowlist (admin) |
| `/removeuser` | Command | Remove user from allowlist (admin) |
| `/users` | Command | List allowed users (admin) |
| `cancel:*` | Callback | Cancel specific QStash reminder |
| `noop` | Callback | No-op for disabled buttons |
| `*` (any text) | Message | Parse and create meeting |

### 3. QStash (Upstash)

Delayed message delivery for reminders:

- **Main reminder**: 45 min before meeting → `/reminder` with `type=main`
- **Urgent reminder**: 5 min before meeting → `/reminder` with `type=urgent`
- Max delay: 7 days (free tier limit)
- Auth: `Bearer` token + `X-Reminder-Secret` header forwarding

### 4. Telethon (Userbot)

Sends personal DMs to meeting participants:

- Lazy-loaded (saves ~1-2 sec cold start)
- Uses `StringSession` (no file system needed on serverless)
- One connection per reminder, sends to all usernames, then disconnects
- Called from `/reminder` endpoint, not from webhook

### 5. Redis (Upstash)

Stores dynamic user allowlist:

- Key: `allowed_users` (Redis Set)
- Values: Telegram user IDs as strings
- Fallback: `ALLOWED_USER_IDS` env variable
- Empty set = access for everyone

---

## Timezone Conversion

Input time is **Istanbul (Europe/Istanbul)**. Conversion to 7 cities using `zoneinfo` (DST-aware):

```
Istanbul (input) → UTC → Riga, Tel-Aviv, Rome, Bishkek, Beijing, Los Angeles
```

If Riga and Tel-Aviv times match → merged: `19:00 Riga;Tel-Aviv`

---

## Security

| Layer | Mechanism |
|---|---|
| Webhook auth | `X-Telegram-Bot-Api-Secret-Token` header |
| Reminder endpoint | `X-Reminder-Secret` custom header |
| User access | Redis allowlist + env fallback |
| Admin commands | `ADMIN_USER_IDS` check |
| Input sanitization | `html.escape()` for all user input |
| Username validation | Regex `^[a-zA-Z0-9_]{5,32}$` |

---

## State Management

| State | Storage | Persistence |
|---|---|---|
| Allowlist | Upstash Redis | ✅ Persistent |
| QStash cancel mapping | In-memory `qstash_id_map` | ❌ Per-instance |
| Last QStash msg ID | In-memory `last_qstash_msg` | ❌ Per-instance |

> ⚠️ In-memory state is lost on each cold start. Inline cancel buttons (stored in Telegram message) are the reliable cancellation method.

---

## Environment Variables

| Variable | Required | Used by |
|---|---|---|
| `BOT_TOKEN` | ✅ | TeleBot |
| `QSTASH_TOKEN` | ✅ | QStash publish/cancel |
| `APP_HOST` | ✅ | QStash callback URL |
| `TG_API_ID` | For DMs | Telethon |
| `TG_API_HASH` | For DMs | Telethon |
| `TELETHON_SESSION` | For DMs | Telethon |
| `WEBHOOK_SECRET` | Recommended | Webhook verification |
| `REMINDER_SECRET` | Recommended | `/reminder` protection |
| `UPSTASH_REDIS_REST_URL` | For allowlist | Redis client |
| `UPSTASH_REDIS_REST_TOKEN` | For allowlist | Redis client |
| `ADMIN_USER_IDS` | Recommended | Admin commands |
| `ALLOWED_USER_IDS` | Optional | Env fallback allowlist |

---

## Infrastructure

```
GitHub repo ──git push──► Vercel (auto-deploy)
                              │
                         api/index.py
                              │
                    ┌─────────┼─────────┐
                    │         │         │
               Telegram   Upstash    Upstash
               Bot API    QStash     Redis
                              │
                         Telethon
                        (userbot DMs)
```

All services on free tiers. Zero cost. Zero maintenance.
