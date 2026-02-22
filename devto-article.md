---
title: I Built a Telegram Bot That Solves the "What Time Is It For You?" Problem
published: false
description: A serverless Telegram bot that converts one message into a timezone-aware meeting card with Google Calendar link and personal DM reminders.
tags: telegram, python, serverless, opensource
cover_image: https://raw.githubusercontent.com/maximosovsky/teleinviter/main/inviter-link-cover.jpg
---

"Can we do 6 PM your time? Wait, what time zone are you in again?"

I've had this conversation hundreds of times. I work with people across 7 timezones — from Los Angeles to Bishkek. Every meeting started the same way: open [World Time Buddy](https://www.worldtimebuddy.com/), convert times, paste the result into Telegram, hope nobody gets confused.

But the real problem wasn't the conversion. It was everything that happens after.

## The Actual Problem

Meetings happen in messengers. Not everyone knows each other's email. So nobody adds you to Google Calendar. You get a Zoom link in a Telegram chat, and that's it — no reminder, no calendar event, just a message you'll scroll past and forget.

I needed three things:
1. **Automatic timezone conversion** — type the time once, everyone sees it in their city
2. **A Google Calendar link** — one click to add the meeting, no email required
3. **DM reminders** — because group chat messages get buried

So I built a Telegram bot that does all three from a single message.

## How It Works

Send the bot one line:

```
Strategy Call, 15.03.2026, 18:00, https://zoom.us/j/123456, @alex @maria
```

It responds with a card like this:

```
📅 Strategy Call
📆 Saturday, 15 March 2026

🕐 17:00 Riga; Tel-Aviv
🕐 17:00 Rome
🕐 18:00 Istanbul
🕐 20:00 Bishkek
🕐 01:00 Beijing (+1 day)
🕐 08:00 Los Angeles

🔗 https://zoom.us/j/123456

📲 Add to Calendar  ❌ Cancel Reminder
```

Then, 45 minutes before the meeting, every participant gets a personal DM: *"Reminder: Strategy Call starts in 45 minutes."* And another one 5 minutes before.

## The Stack (All Free Tier)

| Service | Role | Cost |
|---------|------|------|
| [Vercel](https://vercel.com/) | Hosting (serverless) | $0 |
| [Upstash QStash](https://upstash.com/) | Delayed reminders | $0 |
| [Upstash Redis](https://upstash.com/) | User allowlist | $0 |
| [Telethon](https://docs.telethon.dev/) | Personal DMs | $0 |
| [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) | Bot interface | $0 |

**Total infrastructure cost: $0/month.** Everything runs on free tiers.

The entire bot lives in one file — `api/index.py`. Deploy with `git push`. No servers, no Docker, no maintenance.

## The Hard Parts

### Why Telethon (and why it's risky)

Telegram Bot API has a fundamental limitation: **bots can't DM users who haven't started a conversation with the bot.** So if I invite `@alex` to a meeting, the bot can't send Alex a reminder — Alex never messaged the bot.

The workaround: [Telethon](https://docs.telethon.dev/), a userbot library. It sends DMs from a real Telegram account, not a bot. This bypasses the restriction — but Telegram actively fights spam from userbots. Send too many DMs too fast, and your account gets a `FloodWaitError` or worse — a permanent ban.

My AI assistant kept warning me: *"Don't use Telethon, Telegram will block your account."* I used it anyway, with rate limiting and careful batching. So far, no ban.

### The 64-Byte Bug

Telegram limits `callback_data` (the hidden payload in inline buttons) to 64 bytes. [QStash](https://upstash.com/) message IDs are long. So when the bot tried to create a "Cancel Reminder" button with the full QStash ID, Telegram threw `BUTTON_DATA_INVALID`.

The fix: store a short numeric key (`cancel:1`, `cancel:2`) in the button, and map it to the full QStash ID server-side. Simple, but it took a debugging session to figure out — we only saw the real error after adding detailed error messages to the bot's responses.

### DST Is a Nightmare

Timezone conversion sounds simple until you hit Daylight Saving Time. Riga and Tel-Aviv are sometimes in the same timezone, sometimes not. The bot uses Python's `zoneinfo` with IANA timezone database — proper DST-aware conversion, not hardcoded UTC offsets.

When two cities end up at the same time, the bot merges them: `17:00 Riga; Tel-Aviv`.

## Architecture

```
User → Telegram → Vercel (webhook)
                       │
                  api/index.py
                  (Flask + Bot)
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   Upstash Redis    QStash      Telegram API
   (allowlist)   (2 reminders)  (card + buttons)
                       │
                  ┌────┴────┐
                  │         │
             -45 min    -5 min
                  │         │
             /reminder  /reminder
                  │         │
              Bot msg    Bot msg
              + DMs      + DMs
              (Telethon) (Telethon)
```

Security layers:
- Webhook verification via `X-Telegram-Bot-Api-Secret-Token`
- Reminder endpoint protected by custom `X-Reminder-Secret` header
- Dynamic allowlist in Redis (only approved users can create meetings)
- Admin roles for managing the allowlist
- Input sanitization with `html.escape()`

## What I Learned

**1. Infrastructure beats features.**

The bot has ~10 features (timezones, reminders, DMs, calendar, allowlist, admin roles, cancel buttons). But the real value is the architecture: one file, zero cost, deploy with `git push`. Features are easy to add when the foundation is solid.

**2. Free tiers are surprisingly generous.**

After months of usage: 37 QStash messages total, 16 Redis commands, 0 bandwidth. The free tier limits (1,000 QStash messages/day, 500K Redis commands/month) are absurd overkill for a personal tool.

**3. The Telethon trade-off is real.**

Userbot DMs are the killer feature — and the biggest risk. Telegram can ban your account at any time. For a personal tool, the risk is acceptable. For a product with thousands of users, you'd need a different approach.

**4. AI debugging is best when it shows, not tells.**

The `BUTTON_DATA_INVALID` bug was invisible — we only saw "⚠️ Reminder failed." The fix wasn't in the logic; it was adding `str(e)` to the error message so we could see the real problem in Telegram. AI suggested this in one step.

## Try It

The bot is live: [@inviterLinkBot](https://t.me/inviterLinkBot)

Source code: [github.com/maximosovsky/teleinviter](https://github.com/maximosovsky/teleinviter)

Deploy your own in 5 minutes — you'll need a [Telegram Bot Token](https://t.me/BotFather), an [Upstash](https://upstash.com/) account, and a [Vercel](https://vercel.com/) account. All free.

---

*Building in public, one bot at a time. Follow the journey: [LinkedIn](https://www.linkedin.com/in/osovsky/) · [GitHub](https://github.com/maximosovsky)*
