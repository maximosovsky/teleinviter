import telebot
from datetime import datetime, timedelta, timezone
import urllib.parse
import os
import requests
import json
import asyncio
import re
import http.client
from html import escape
from flask import Flask, request

# Telethon импортируется лениво — только при отправке ЛС (экономит ~1-2 сек на cold start)

# Инициализация
API_TOKEN = os.getenv('BOT_TOKEN')
QSTASH_TOKEN = os.getenv('QSTASH_TOKEN')
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TELETHON_SESSION = os.getenv('TELETHON_SESSION')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
APP_HOST = os.getenv('APP_HOST')

# Allowlist: Telegram user IDs, которым разрешено создавать встречи
ALLOWED_USER_IDS = os.getenv('ALLOWED_USER_IDS', '')
ALLOWED_USERS = set()
if ALLOWED_USER_IDS:
    ALLOWED_USERS = {int(uid.strip()) for uid in ALLOWED_USER_IDS.split(',') if uid.strip()}

bot = telebot.TeleBot(API_TOKEN, threaded=False)
app = Flask(__name__)

# --- Утилиты безопасности ---

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{5,32}$')

def is_valid_username(username):
    """Валидация Telegram username."""
    return bool(USERNAME_RE.match(username))

def is_user_allowed(user_id):
    """Проверка allowlist. Если список пуст — доступ для всех."""
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

# --- Маршруты ---

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        # Проверка secret_token от Telegram
        if WEBHOOK_SECRET:
            token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
            if token != WEBHOOK_SECRET:
                return 'Forbidden', 403

        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK', 200
        except Exception as e:
            print(f"Error processing update: {e}")
            return 'Error', 500
    else:
        return '''
        <html>
            <head>
                <title>InviterLink Bot</title>
                <link rel="icon" href="/logo.png?v=3" type="image/png">
                <style>
                    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f0f2f5; }
                    .card { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); text-align: center; }
                    h1 { color: #0088cc; margin: 0; font-size: 24px; }
                    p { color: #666; margin-top: 10px; font-size: 16px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>🚀 InviterLink Bot is Running!</h1>
                    <p>Бот активен и готов к работе в Telegram.</p>
                </div>
            </body>
        </html>
        ''', 200

# Отправка личного сообщения через Telethon (userbot)
async def send_userbot_message(username, text):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(TELETHON_SESSION), int(TG_API_ID), TG_API_HASH)
    await client.connect()
    try:
        await client.send_message(username, text)
    finally:
        await client.disconnect()

# Вход для будильника (QStash)
@app.route('/reminder', methods=['POST'])
def reminder_trigger():

    try:
        data = request.json
        chat_id = data.get('chat_id')
        zoom = data.get('zoom', '')
        target_username = data.get('target_username')
        title = data.get('title', 'Встреча')

        # Экранирование для HTML
        safe_zoom = escape(zoom)

        # Напоминание в чат бота
        bot.send_message(chat_id, 
            f"⚡️ На всякий случай, напоминаю,\n<b>ZOOM через 40 минут</b>\n{safe_zoom}", 
            parse_mode='HTML', disable_web_page_preview=True)

        # Личное сообщение участнику через userbot
        if target_username and TELETHON_SESSION and TG_API_ID and TG_API_HASH:
            # Валидация username
            if not is_valid_username(target_username):
                print(f"Invalid username rejected: {target_username}")
                return 'OK', 200

            safe_title = escape(title)
            msg = f"👋 Привет! Напоминаю о встрече:\n\n📌 {safe_title}\n🔗 {zoom}\n\n⏰ Через ~40 минут"
            try:
                asyncio.run(send_userbot_message(target_username, msg))
                bot.send_message(chat_id, f"✅ Личное сообщение отправлено @{escape(target_username)}")
            except Exception as e:
                print(f"Telethon error for @{target_username}: {e}")
                bot.send_message(chat_id, f"⚠️ Не удалось отправить личное напоминание")
        elif target_username:
            print(f"Telethon not configured, cannot send DM to @{target_username}")
    except Exception as e:
        print(f"Reminder error: {e}")
    return 'OK', 200

@bot.message_handler(commands=['start'])
def start(message):
    if not is_user_allowed(message.from_user.id):
        return
    bot.send_message(message.chat.id, "Бот готов! Пришли: <code>Тема, Дата, Время Ist, Ссылка, @username</code>\n(@username — необязательно)", parse_mode='HTML')

@bot.message_handler(func=lambda m: True)
def create_meeting(message):
    if not is_user_allowed(message.from_user.id):
        return

    try:
        parts = [p.strip() for p in message.text.split(',')]
        if len(parts) < 4: raise ValueError
        title, date_val, time_val, zoom = parts[:4]
        target_username = parts[4].lstrip('@') if len(parts) >= 5 else None

        # Валидация username
        if target_username and not is_valid_username(target_username):
            bot.send_message(message.chat.id, "❌ Некорректный @username (допустимы: буквы, цифры, _, длина 5–32)")
            return

        # Логика времени
        naive_dt = datetime.strptime(f"{date_val} {time_val}", "%d.%m.%Y %H:%M")
        ist_tz = timezone(timedelta(hours=3))
        meeting_dt_ist = naive_dt.replace(tzinfo=ist_tz)
        now_ist = datetime.now(timezone.utc).astimezone(ist_tz)

        # Форматирование
        months = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
        days_short = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
        date_text = f"{meeting_dt_ist.day} {months[meeting_dt_ist.month-1]} {meeting_dt_ist.year}"
        day_name = days_short[meeting_dt_ist.weekday()]

        # Расчет городов
        h, m = meeting_dt_ist.hour, meeting_dt_ist.minute
        def calc_city(offset):
            nh = (h + offset + 24) % 24
            return f"{nh:02d}:{m:02d}"
            
        cities = f"{calc_city(-1)} Riga;Tel-Aviv / {calc_city(-2)} Rome / {calc_city(3)} Bishkek / {calc_city(5)} Beijing / {calc_city(-11)} Los Angeles"

        # Ссылка в календарь (1 час)
        m_utc_start = meeting_dt_ist.astimezone(timezone.utc)
        iso_start = m_utc_start.strftime("%Y%m%dT%H%M%SZ")
        iso_end = (m_utc_start + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        gcal = "https://www.google.com/calendar/render?" + urllib.parse.urlencode({
            "action": "TEMPLATE", "text": title, "dates": f"{iso_start}/{iso_end}",
            "details": f"Zoom: {zoom}", "ctz": "UTC"
        })

        # Экранирование пользовательского ввода для HTML
        safe_title = escape(title)
        safe_zoom = escape(zoom)

        # Ответ в Телеграм
        res = (f"<b>{safe_title}</b>\n"
               f"⚡️ <b>{date_text}</b> в <b>{day_name}</b> в <b>{time_val} Ist</b>\n"
               f"<code>{cities}</code>\n\n"
               f"<b>ZOOM</b> — {safe_zoom}\n\n"
               f"📲 <a href='{gcal}'>Добавить в календарь</a>")

        bot.send_message(message.chat.id, res, parse_mode='HTML', disable_web_page_preview=True)

        # Будильник QStash (45 мин до встречи)
        if QSTASH_TOKEN:
            reminder_time = meeting_dt_ist - timedelta(minutes=45)
            delay = int((reminder_time - now_ist).total_seconds())

            if delay > 0:
                if not APP_HOST:
                    print("APP_HOST not set, skipping QStash reminder")
                else:
                    # Нормализация APP_HOST: убираем схему и trailing slash
                    clean_host = APP_HOST.replace("https://", "").replace("http://", "").rstrip("/")
                    qstash_path = f"/v2/publish/https://{clean_host}/reminder"
                    
                    qstash_headers = {
                        "Authorization": f"Bearer {QSTASH_TOKEN}",
                        "Content-Type": "application/json",
                        "Upstash-Delay": f"{delay}s"
                    }
                    payload = {"chat_id": message.chat.id, "zoom": zoom, "title": title}
                    if target_username:
                        payload["target_username"] = target_username
                    
                    # http.client не нормализует URL (requests ломает https:// в пути)
                    conn = http.client.HTTPSConnection("qstash.upstash.io", timeout=10)
                    conn.request("POST", qstash_path, body=json.dumps(payload), headers=qstash_headers)
                    resp = conn.getresponse()
                    resp_body = resp.read().decode()
                    conn.close()
                    print(f"QStash path: {qstash_path}")
                    print(f"QStash response: {resp.status} {resp_body}")
                    
                    if 200 <= resp.status < 300:
                        remind_text = f"🔔 Напомню в {reminder_time.strftime('%H:%M')} Ist"
                        if target_username:
                            remind_text += f" (+ напишу @{escape(target_username)})"
                        bot.send_message(message.chat.id, remind_text, parse_mode='HTML')
                    else:
                        bot.send_message(message.chat.id, f"⚠️ QStash {resp.status}: {resp_body[:300]}")

    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка формата! Пришли: Тема, ДД.ММ.ГГГГ, ЧЧ:ММ, Zoom-ссылка, @username")

# Экспорт для Vercel
app = app
