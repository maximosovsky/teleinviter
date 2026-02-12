# 🗓 InviterLink Bot

Telegram-бот для организации встреч. Создаёт карточку встречи с пересчётом времени по городам, ссылкой в Google Calendar, напоминанием за 45 минут и личными сообщениями участникам.

![logo](logo.png)

## Возможности

- **Карточка встречи** — название, дата, день недели, время
- **DST-aware часовые пояса** — автопересчёт для 7 городов через `zoneinfo` (IANA)
- **Google Calendar** — inline-кнопка «📲 Добавить в календарь»
- **Напоминание** — за 45 минут через QStash (до 7 дней вперёд)
- **Отмена напоминания** — inline-кнопка «❌ Отменить» или `/cancel`
- **Несколько участников** — до 5 `@username` через пробел, каждому придёт ЛС через Telethon
- **Безопасность** — webhook secret, allowlist, защита `/reminder` эндпоинта, экранирование ввода

## Как пользоваться

Отправь боту сообщение в формате:

```
Тема, ДД.ММ.ГГГГ, ЧЧ:ММ, Ссылка, @user1 @user2
```

`@username` — необязательно (можно несколько через пробел).

**Примеры:**

```
Стратегия, 15.03.2026, 18:00, https://zoom.us/j/123456
```

```
Созвон, 13.02.2026, 20:00, https://zoom.us/j/789, @ivan @maria
```

### Команды

| Команда | Описание |
|---|---|
| `/start` | Справка по формату |
| `/cancel` | Отменить последнее напоминание |

## Стек

| Технология | Роль |
|---|---|
| Python + Flask | HTTP-сервер (serverless) |
| pyTelegramBotAPI | Telegram Bot API |
| Telethon | Userbot для личных сообщений |
| QStash (Upstash) | Отложенные напоминания (до 7 дней) |
| zoneinfo | DST-aware часовые пояса |
| Vercel | Деплой |

## Архитектура

```
Пользователь → Telegram → Vercel (webhook /)
                                    │
                          ┌─────────┴──────────┐
                          │   api/index.py      │
                          │   Flask + Bot        │
                          └─────────┬──────────┘
                                    │
                     ┌──────────────┼───────────────┐
                     │              │               │
               QStash publish   Карточка +      Callback
               (delay Ns)     inline-кнопки     (отмена)
                     │                              │
                     ▼                              ▼
              /reminder endpoint           QStash DELETE
                     │                     /v2/messages/{id}
              ┌──────┴──────┐
              │             │
         Напоминание    Telethon ЛС
         в чат бота     участникам
```

### Города и таймзоны

| Город | IANA зона |
|---|---|
| Riga | `Europe/Riga` |
| Tel-Aviv | `Asia/Tel_Aviv` |
| Rome | `Europe/Rome` |
| Istanbul | `Europe/Istanbul` |
| Bishkek | `Asia/Bishkek` |
| Beijing | `Asia/Shanghai` |
| Los Angeles | `America/Los_Angeles` |

Время вводится по Istanbul (IST). Если Riga и Tel-Aviv совпадают — они объединяются: `19:00 Riga;Tel-Aviv`.

## Деплой на Vercel

### 1. Переменные окружения

Добавь в Vercel → Settings → Environment Variables:

| Переменная | Описание | Обязательна |
|---|---|---|
| `BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) | ✅ |
| `QSTASH_TOKEN` | Токен [Upstash QStash](https://upstash.com/) | ✅ |
| `APP_HOST` | Домен Vercel (например `teleinviter.vercel.app`) | ✅ |
| `TG_API_ID` | API ID приложения с [my.telegram.org](https://my.telegram.org/) | Для ЛС |
| `TG_API_HASH` | API Hash с my.telegram.org | Для ЛС |
| `TELETHON_SESSION` | StringSession (см. ниже) | Для ЛС |
| `WEBHOOK_SECRET` | Секрет для верификации вебхуков Telegram | Рекомендуется |
| `REMINDER_SECRET` | Секрет для защиты `/reminder` эндпоинта | Рекомендуется |
| `ALLOWED_USER_IDS` | Список Telegram user ID через запятую | Опционально |

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
├── .gitignore              # Исключения из Git
└── README.md
```

## Ограничения

- **QStash free tier** — максимальная задержка 7 дней (604800 сек)
- **Vercel serverless** — состояние `last_qstash_msg` не сохраняется между инстансами (для надёжной отмены — используй inline-кнопку)
- **Telethon** — не отправлять слишком часто, чтобы избежать блокировки аккаунта

## Лицензия

MIT
