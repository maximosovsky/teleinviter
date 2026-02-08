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

bot = telebot.TeleBot(API_TOKEN, threaded=False)
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK', 200
        except Exception as e:
            print(f"Error processing update: {e}")
            return 'Error', 500
    else:
        # Красивая страница для браузера с иконкой
        return '''
        <html>
            <head>
                <title>InviterLink Bot</title>
                <link rel="icon" href="/favicon.ico?v=2" type="image/x-icon">
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

# Вход для будильника
@app.route('/reminder', methods=['POST'])
def reminder_trigger():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        zoom = data.get('zoom')
        bot.send_message(chat_id, 
            f"⚡️ На всякий случай, напоминаю,\n<b>ZOOM через 40 минут</b>\n{zoom}", 
            parse_mode='HTML', disable_web_page_preview=True)
    except Exception as e:
        print(f"Reminder error: {e}")
    return 'OK', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Бот готов! Пришли: <code>Тема, Дата, Время Ist, Ссылка</code>", parse_mode='HTML')

@bot.message_handler(func=lambda m: True)
def create_meeting(message):
    try:
        parts = [p.strip() for p in message.text.split(',')]
        if len(parts) < 4: raise ValueError
        title, date_val, time_val, zoom = parts

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
            
        # Твой обновленный список городов
        cities = f"{calc_city(-1)} Riga;Tel-Aviv / {calc_city(-2)} Rome / {calc_city(3)} Bishkek / {calc_city(5)} Иркутск / {calc_city(-11)} LA"

        # Ссылка в календарь (1 час)
        m_utc_start = meeting_dt_ist.astimezone(timezone.utc)
        iso_start = m_utc_start.strftime("%Y%m%dT%H%M%SZ")
        iso_end = (m_utc_start + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        gcal = "https://www.google.com/calendar/render?" + urllib.parse.urlencode({
            "action": "TEMPLATE", "text": title, "dates": f"{iso_start}/{iso_end}",
            "details": f"Zoom: {zoom}", "ctz": "UTC"
        })

        # Ответ в Телеграм
        res = (f"<b>{title}</b>\n"
               f"⚡️ <b>{date_text}</b> в <b>{day_name}</b> в <b>{time_val} Ist</b>\n"
               f"<code>{cities}</code>\n\n"
               f"<b>ZOOM</b> — {zoom}\n\n"
               f"📲 <a href='{gcal}'>Добавить в календарь</a>")

        bot.send_message(message.chat.id, res, parse_mode='HTML', disable_web_page_preview=True)

        # Будильник QStash
        if QSTASH_TOKEN:
            reminder_time = meeting_dt_ist - timedelta(minutes=45)
            delay = int((reminder_time - now_ist).total_seconds())

            if delay > 0:
                target_url = f"https://{request.host}/reminder"
                headers = {
                    "Authorization": f"Bearer {QSTASH_TOKEN}",
                    "Content-Type": "application/json",
                    "Upstash-Delay": f"{delay}s"
                }
                payload = {"chat_id": message.chat.id, "zoom": zoom}
                requests.post(f"https://qstash.upstash.io/v2/publish/{target_url}", 
                              headers=headers, data=json.dumps(payload), timeout=5)
                
                bot.send_message(message.chat.id, f"🔔 Напомню в {reminder_time.strftime('%H:%M')} Ist")

    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка формата!")

# Экспорт для Vercel
app = app
