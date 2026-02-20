<div align="center">
  <img src="logo.png" alt="InviterLink Bot" width="120"/>
  <h1>🗓 InviterLink Bot</h1>
  <p>Telegram bot for timezone-aware meeting scheduling with reminders & DMs</p>

  ![License](https://img.shields.io/badge/license-CC%20BY--SA%204.0-green)
  ![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white)
  ![Vercel](https://img.shields.io/badge/deploy-Vercel-black?logo=vercel)
  [![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-26A5E4?logo=telegram&logoColor=white)](https://t.me/inviterLinkBot)

  [Quick Start](#-usage) · [Features](#-features) · [Deploy](#-deploy-to-vercel) · [Stack](#-stack)
</div>

---

> **One message → meeting card with timezone conversion, calendar link, and personal reminders.**
> Send the bot a title, date, time, and link — it builds a rich card for 7 cities, schedules DM reminders via QStash, and adds a Google Calendar button.

---

## 💡 Why InviterLink?

| Feature | InviterLink | Reminder bots | Calendar bots | Cal.com |
|---|:---:|:---:|:---:|:---:|
| Multi-timezone card (7 cities) | ✅ | ❌ | ❌ | ❌ |
| Personal DMs via Telethon | ✅ | ❌ | ❌ | ❌ |
| Dual reminders (45 min + 5 min) | ✅ | ⚠️ single | ❌ | ✅ |
| Google Calendar one-click | ✅ | ❌ | ✅ | ✅ |
| Serverless & free (Vercel) | ✅ | ⚠️ VPS | ⚠️ VPS | ❌ paid |

---

## ✨ Features

- **Meeting card** — title, date, day of week, time
- **DST-aware timezones** — auto-conversion for 7 cities via `zoneinfo` (IANA)
- **Google Calendar** — inline button "📲 Add to Calendar"
- **Reminders** — 45 min and 5 min before via QStash (up to 7 days), with meeting title and link. Both reminders send DMs to participants
- **Cancel reminder** — inline button "❌ Cancel" or `/cancel`
- **Multiple participants** — up to 5 `@usernames` space-separated, each gets a DM via Telethon
- **Dynamic allowlist** — manage access via `/adduser`, `/removeuser`, `/users` (stored in Upstash Redis, env fallback)
- **Admin roles** — only admins (`ADMIN_USER_IDS`) can manage the allowlist; regular users can only create meetings
- **Security** — webhook secret, allowlist, `/reminder` endpoint protection, input sanitization

---

## 🚀 Usage

Send the bot a message in this format:

```
Title, DD.MM.YYYY, HH:MM, Link, @user1 @user2
```

`@username` is optional (multiple allowed, space-separated).

**Examples:**

```
Strategy, 15.03.2026, 18:00, https://zoom.us/j/123456
```

```
Standup, 13.02.2026, 20:00, https://zoom.us/j/789, @osowski @maxim_osovsky
```

### Commands

| Command | Description |
|---|---|
| `/start` | Show format help |
| `/cancel` | Cancel last reminder |
| `/adduser <ID>` | Add user to allowlist (admin only) |
| `/removeuser <ID>` | Remove user from allowlist (admin only) |
| `/users` | Show allowed users (admin only) |

---

## 🏗 Stack

| Technology | Role |
|---|---|
| Python + Flask | HTTP server (serverless) |
| pyTelegramBotAPI | Telegram Bot API |
| Telethon | Userbot for direct messages |
| QStash (Upstash) | Delayed reminders (up to 7 days) |
| Redis (Upstash) | Dynamic allowlist storage |
| zoneinfo | DST-aware timezones |
| Vercel | Deployment |

```
teleinv/
├── api/
│   └── index.py           # Main bot logic
├── generate_session.py     # Telethon StringSession generator
├── logo.png                # Bot logo
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel routing
├── .gitignore              # Git exclusions
└── README.md
```

---

## 🔧 Architecture

<details>
<summary>Click to expand</summary>

```
User → Telegram → Vercel (webhook /)
                                │
                      ┌─────────┴──────────┐
                      │   api/index.py      │
                      │   Flask + Bot        │
                      └─────────┬──────────┘
                                │
                         is_user_allowed?
                                │
          ┌─────────────┬───────┼───────────────┐
          │             │       │               │
    Upstash Redis   QStash    Card +        Callback
    (allowlist)   (delay Ns)  inline btns   (cancel)
          │         │                          │
     is_admin?      ▼                          ▼
          │    /reminder endpoint      QStash DELETE
          ▼         │                /v2/messages/{id}
    /adduser   ┌────┴─────┐
    /removeuser│ main(45m)│ urgent(5m)
    /users     ├──────────┤
               │          │
          Reminder +  Reminder +
          Telethon DM Telethon DM
```

### Cities & Timezones

| City | IANA Zone |
|---|---|
| Riga | `Europe/Riga` |
| Tel-Aviv | `Asia/Tel_Aviv` |
| Rome | `Europe/Rome` |
| Istanbul | `Europe/Istanbul` |
| Bishkek | `Asia/Bishkek` |
| Beijing | `Asia/Shanghai` |
| Los Angeles | `America/Los_Angeles` |

Time input is in Istanbul (IST). If Riga and Tel-Aviv match — they merge: `19:00 Riga;Tel-Aviv`.

</details>

---

## 🚀 Deploy to Vercel

<details>
<summary>1. Environment Variables</summary>

Add to Vercel → Settings → Environment Variables:

| Variable | Description | Required |
|---|---|---|
| `BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) | ✅ |
| `QSTASH_TOKEN` | [Upstash QStash](https://upstash.com/) token | ✅ |
| `APP_HOST` | Vercel domain (e.g. `teleinviter.vercel.app`) | ✅ |
| `TG_API_ID` | App API ID from [my.telegram.org](https://my.telegram.org/) | For DMs |
| `TG_API_HASH` | API Hash from my.telegram.org | For DMs |
| `TELETHON_SESSION` | StringSession (see below) | For DMs |
| `WEBHOOK_SECRET` | Secret for Telegram webhook verification | Recommended |
| `REMINDER_SECRET` | Secret for `/reminder` endpoint protection | Recommended |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL | For allowlist |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST token | For allowlist |
| `ADMIN_USER_IDS` | Comma-separated admin Telegram user IDs | Recommended |
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs (env fallback) | Optional |

</details>

<details>
<summary>2. Generate Telethon Session</summary>

```bash
pip install telethon
python generate_session.py
```

The script will ask for `API_ID` and `API_HASH`, authorize your account, and output a session string. Copy it to the `TELETHON_SESSION` variable.

</details>

<details>
<summary>3. Set Webhook</summary>

After deploying to Vercel, set the webhook:

```
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<your-domain>.vercel.app/&secret_token=<WEBHOOK_SECRET>
```

</details>

---

## 🌐 Use Cases

- Schedule multi-timezone team calls
- Auto-remind participants via DM
- One-click Google Calendar integration

---

## ⚠️ Limitations & Quotas

<details>
<summary>Click to expand</summary>

### QStash (Upstash) — Free tier

| Limit | Value |
|---|---|
| Max delay | 7 days (604,800 sec) |
| Messages/day | 500 |
| Messages/sec | 50 |
| Retries on failure | 3 |

🔗 Check usage: [console.upstash.com](https://console.upstash.com/) → QStash → Usage

### Redis (Upstash) — Free tier

| Limit | Value |
|---|---|
| Commands/day | 10,000 |
| DB size | 256 MB |
| Max connections | 1,000 |

🔗 Check usage: [console.upstash.com](https://console.upstash.com/) → Redis → Usage

### Vercel — Free tier (Hobby)

| Limit | Value |
|---|---|
| Serverless invocations | 100,000/month |
| Function timeout | 10 sec |
| Bandwidth | 100 GB/month |

🔗 Check usage: [vercel.com/dashboard](https://vercel.com/dashboard) → Usage

### Telethon (Userbot)

| Limit | Value |
|---|---|
| DMs to strangers | ~20–50/day (Telegram flood ban) |
| Session lifetime | Permanent until revoked |

⚠️ `FloodWaitError` = sending too fast. Session can be revoked at [my.telegram.org](https://my.telegram.org/)

### Telegram Bot API

| Limit | Value |
|---|---|
| `callback_data` size | 64 bytes |
| Messages/sec per chat | 1 (global: 30/sec) |
| Inline buttons per row | 8 |

### Other

- **Vercel serverless** — `last_qstash_msg` state is not persisted across instances (use inline button for reliable cancellation)

</details>

---

## 🤝 Contributing

Feedback and PRs are welcome! Feel free to open issues.

## 📄 License

[Maxim Osovsky](https://www.linkedin.com/in/osovsky/). Licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
