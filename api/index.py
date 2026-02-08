import telebot
from datetime import datetime, timedelta, timezone
import urllib.parse
import os
import requests
import json
from flask import Flask, request

# Инициализация
API_TOKEN = os.getenv('BOT_TOKEN')
QSTASH_TOKEN = os.getenv('QSTASH_TOKEN')
VERCEL_URL = f"https://{os.getenv('VERCEL_URL')}" # Авто-определение твоего адреса

bot = telebot.TeleBot(API_TOKEN, threaded=False)
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return '<h1>Zonely Bot is Running!</h1>', 200

# СЕКРЕТНЫЙ ВХОД ДЛЯ НАПОМИНАНИЯ
@app.route('/reminder', methods=['POST'])
def reminder_trigger():
    data = request.json
    chat_id = data.get('chat_id')
    zoom = data.get('zoom')
    
    bot.send_message(chat_id, 
        f"⚡️ На всякий случай, напоминаю,\n<b>ZOOM через 40 минут</b>\n{zoom}", 
        parse_mode='HTML', disable_web_page_preview=True)
    return 'OK', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Бот готов! Пришли: Тема, Дата, Время Ist, Ссылка")

@bot.message_handler(func=lambda m: True)
def create_meeting(message):
    try:
        parts = [p.strip() for p in message.text.split(',')]
        title, date_val, time_val, zoom = parts[0], parts[1], parts[2], parts[3]

        naive_dt = datetime.strptime(f"{date_val} {time_val}", "%d.%m.%Y %H:%M")
        ist_tz = timezone(timedelta(hours=3))
        meeting_dt_ist = naive_dt.replace(tzinfo=ist_tz)
        now_ist = datetime.now(timezone.utc).astimezone(ist_tz)

        # Ссылка в календарь
        m_utc_start = meeting_dt_ist.astimezone(timezone.utc)
        iso_start = m_utc_start.strftime("%Y%m%dT%H%M%SZ")
        iso_end = (m_utc_start + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        gcal = "https://www.google.com/calendar/render?" + urllib.parse.urlencode({
            "action": "TEMPLATE", "text": title, "dates": f"{iso_start}/{iso_end}",
            "details": f"Zoom: {zoom}", "ctz": "UTC"
        })

        # Ответ в Телеграм
        res = (f"<b>{title}</b>\n⚡️ {meeting_dt_ist.day}.{meeting_dt_ist.month} в {time_val} Ist\n\n"
               f"<b>ZOOM</b> — {zoom}\n\n📲 <a href='{gcal}'>Добавить в календарь</a>")
        bot.send_message(message.chat.id, res, parse_mode='HTML', disable_web_page_preview=True)

        # СТАВИМ БУДИЛЬНИК ЧЕРЕЗ QSTASH
        if QSTASH_TOKEN:
            reminder_time = meeting_dt_ist - timedelta(minutes=45)
            delay = int((reminder_time - now_ist).total_seconds())

            if delay > 0:
                # Отправляем запрос на отложенный вызов нашего же бота
                target_url = f"{request.url_root}reminder"
                headers = {
                    "Authorization": f"Bearer {QSTASH_TOKEN}",
                    "Content-Type": "application/json",
                    "Upstash-Delay": f"{delay}s"
                }
                payload = {"chat_id": message.chat.id, "zoom": zoom}
                requests.post(f"https://qstash.upstash.io/v2/publish/{target_url}", 
                              headers=headers, data=json.dumps(payload))
                
                bot.send_message(message.chat.id, f"🔔 Напомню в {reminder_time.strftime('%H:%M')} Ist")

    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка формата!")

app = app
