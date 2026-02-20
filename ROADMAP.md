# 🗺 Roadmap — InviterLink Bot

## ✅ Done

- [x] Meeting card with 7 timezone cities (DST-aware)
- [x] Dual reminders (45 min + 5 min) via QStash
- [x] Personal DMs via Telethon userbot
- [x] Google Calendar inline button
- [x] Dynamic allowlist (Redis) with admin roles
- [x] Webhook deduplication (Redis `update_id` tracking)
- [x] Telethon rate limiting with FloodWaitError handling

## 🔜 Planned

### Reliability

- [ ] **Persist QStash cancel mapping in Redis** — current `qstash_id_map` is in-memory and lost on cold start. Move to Redis for reliable inline cancel buttons.
- [ ] **Structured logging** — replace `print()` with `logging` module + levels (warning, error) for easier debugging in Vercel Logs.

### Features

- [ ] **Recurring meetings** — syntax like `Standup, every mon, 10:00, link` using QStash Schedules (cron).
- [ ] **RSVP buttons** — ✅/❌ inline buttons for participants to confirm attendance.
- [ ] **User timezone setting** — `/timezone Europe/Riga` to show time in personal zone instead of all 7 cities.
- [ ] **Edit meeting** — inline button "✏️ Edit" to change time/link after creation.

### Quality

- [ ] **Unit tests** — pytest with mocks for QStash, Redis, Telethon.
- [ ] **URL validation** — verify that the link field is a valid URL.
- [ ] **English localization** — `/lang en` command to switch bot language.
