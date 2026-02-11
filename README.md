# 🗓 InviterLink Bot

Telegram-бот для организации встреч. Создаёт карточку встречи с пересчётом времени по городам, ссылкой в Google Calendar и напоминанием за 45 минут.

![logo](logo.png)

## Возможности

- **Карточка встречи** — название, дата, день недели, время
- **Часовые пояса** — автопересчёт для Риги, Рима, Бишкека, Пекина, Лос-Анджелеса
- **Google Calendar** — кликабельная ссылка «Добавить в календарь»
- **Напоминание** — за 45 минут через QStash (Upstash)
- **Личное сообщение** — отправка напоминания участнику через Telethon (userbot)

## Как пользоваться

Отправь боту сообщение в формате:

```
Тема, ДД.ММ.ГГГГ, ЧЧ:ММ, Zoom-ссылка, @username
```

`@username` — необязательный параметр (участник, которому бот напишет лично).

**Пример:**

```
Meeting, 15.03.2026, 18:00, https://us02web.zoom.us/j/8204568026, @ivan
```

## Стек

| Технология | Роль |
|---|---|
| Python + Flask | HTTP-сервер (serverless) |
| pyTelegramBotAPI | Telegram Bot API |
| Telethon | Userbot для личных сообщений |
| QStash (Upstash) | Отложенные напоминания |
| Vercel | Деплой |

## Деплой на Vercel

### 1. Переменные окружения

Добавь в Vercel → Settings → Environment Variables:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) |
| `WEBHOOK_SECRET` | Секретный токен для верификации webhook (передаётся при `setWebhook`) |
| `QSTASH_TOKEN` | Токен [Upstash QStash](https://upstash.com/) |
| `QSTASH_CURRENT_SIGNING_KEY` | Ключ подписи QStash (Dashboard → Signing Keys) |
| `APP_HOST` | Домен приложения, например `your-app.vercel.app` |
| `TG_API_ID` | API ID с [my.telegram.org](https://my.telegram.org/) |
| `TG_API_HASH` | API Hash с my.telegram.org |
| `TELETHON_SESSION` | StringSession (см. ниже) |
| `ALLOWED_USER_IDS` | Telegram user IDs через запятую (если пусто — доступ для всех) |

### 2. Генерация Telethon-сессии

```bash
pip install telethon
python generate_session.py
```

Скрипт запросит `API_ID` и `API_HASH`, авторизует аккаунт и выдаст строку сессии. Скопируй её в переменную `TELETHON_SESSION`.

### 3. Установка Webhook

После деплоя на Vercel установи вебхук:

```
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<your-domain>.vercel.app/&secret_token=<WEBHOOK_SECRET>
```

## Структура проекта

```
teleinv/
├── api/
│   └── index.py           # Основная логика бота
├── generate_session.py     # Генерация Telethon StringSession
├── logo.png                # Логотип бота
├── requirements.txt        # Зависимости Python
├── vercel.json             # Роутинг Vercel
└── README.md
```

## Лицензия

MIT
