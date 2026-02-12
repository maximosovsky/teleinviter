# 🗓 InviterLink Bot

Telegram bot for scheduling meetings. Creates a meeting card with timezone-aware time conversion, Google Calendar link, reminders at 45 and 5 minutes before, and personal messages to participants.

![logo](logo.png)

## Features

- **Meeting card** — title, date, day of week, time
- **DST-aware timezones** — auto-conversion for 7 cities via `zoneinfo` (IANA)
- **Google Calendar** — inline button "📲 Add to Calendar"
- **Reminders** — 45 min and 5 min before via QStash (up to 7 days), with meeting title and link. Both reminders send DMs to participants
- **Cancel reminder** — inline button "❌ Cancel" or `/cancel`
- **Multiple participants** — up to 5 `@usernames` space-separated, each gets a DM via Telethon
- **Security** — webhook secret, allowlist, `/reminder` endpoint protection, input sanitization

## Usage

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

## Stack

| Technology | Role |
|---|---|
| Python + Flask | HTTP server (serverless) |
| pyTelegramBotAPI | Telegram Bot API |
| Telethon | Userbot for direct messages |
| QStash (Upstash) | Delayed reminders (up to 7 days) |
| zoneinfo | DST-aware timezones |
| Vercel | Deployment |

## Architecture

```
User → Telegram → Vercel (webhook /)
                                │
                      ┌─────────┴──────────┐
                      │   api/index.py      │
                      │   Flask + Bot        │
                      └─────────┬──────────┘
                                │
                 ┌──────────────┼───────────────┐
                 │              │               │
           QStash publish   Card +          Callback
           (delay Ns)     inline buttons    (cancel)
                 │                              │
                 ▼                              ▼
           /reminder endpoint           QStash DELETE
                  │                     /v2/messages/{id}
           ┌──────┴──────┐
           │  type=main   │  type=urgent
           │  (45 min)    │  (5 min)
           ├──────────────┤
           │              │
      Reminder +      Reminder +
      Telethon DM     Telethon DM
      to participants to participants
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

## Deploy to Vercel

### 1. Environment Variables

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
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs | Optional |

### 2. Generate Telethon Session

```bash
pip install telethon
python generate_session.py
```

The script will ask for `API_ID` and `API_HASH`, authorize your account, and output a session string. Copy it to the `TELETHON_SESSION` variable.

### 3. Set Webhook

After deploying to Vercel, set the webhook:

```
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<your-domain>.vercel.app/&secret_token=<WEBHOOK_SECRET>
```

## Project Structure

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

## Limitations

- **QStash free tier** — max delay 7 days (604,800 sec)
- **Vercel serverless** — `last_qstash_msg` state is not persisted across instances (use inline button for reliable cancellation)
- **Telethon** — avoid sending too frequently to prevent account ban

## License

MIT
