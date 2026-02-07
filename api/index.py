import telebot
from datetime import datetime, timedelta, timezone
import urllib.parse
import os
from flask import Flask, request

# Инициализация бота
API_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN, threaded=False)

app = Flask(__name__)

# Вебхук: принимает и POST (от Telegram), и GET (от тебя для проверки)
@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK', 200
    else:
        return '<h1>Zonely Bot is Running!</h1>', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Бот на Vercel готов! Пришли данные встречи через запятую:\n<code>Название, 20.03.2026, 18:00, ссылка</code>", parse_mode='HTML')

@bot.message_handler(func=lambda m: True)
def create_meeting(message):
    try:
        parts = [p.strip() for p in message.text.split(',')]
        title, date_val, time_val, zoom = parts[0], parts[1], parts[2], parts[3]

        naive_dt = datetime.strptime(f"{date_val} {time_val}", "%d.%m.%Y %H:%M")
        ist_tz = timezone(timedelta(hours=3))
        meeting_dt_ist = naive_dt.replace(tzinfo=ist_tz)
        
        # Расчет городов
        h, m = meeting_dt_ist.hour, meeting_dt_ist.minute
        def calc_city(offset):
            nh = (h + offset + 24) % 24
            return f"{nh:02d}:{m:02d}"
        cities = f"{calc_city(-1)} Riga;Tel-Aviv / {calc_city(-2)} Rome / {calc_city(3)} Bishkek / {calc_city(5)} Иркутск / {calc_city(-11)} Los Angeles"

        # Ссылка в календарь на 1 час
        m_utc_start = meeting_dt_ist.astimezone(timezone.utc)
        m_utc_end = m_utc_start + timedelta(hours=1)
        iso_start = m_utc_start.strftime("%Y%m%dT%H%M%SZ")
        iso_end = m_utc_end.strftime("%Y%m%dT%H%M%SZ")
        
        gcal = "https://www.google.com/calendar/render?" + urllib.parse.urlencode({
            "action": "TEMPLATE", "text": title, "dates": f"{iso_start}/{iso_end}",
            "details": f"Zoom: {zoom}", "ctz": "UTC"
        })

        months = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
        days = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
        res = (f"<b>{title}</b>\n⚡️ <b>{meeting_dt_ist.day} {months[meeting_dt_ist.month-1]} {meeting_dt_ist.year}</b> в <b>{days[meeting_dt_ist.weekday()]}</b> в <b>{time_val} Ist</b>\n"
               f"<code>{cities}</code>\n\n<b>ZOOM</b> — {zoom}\n\n📲 <a href='{gcal}'>Добавить в календарь</a>")

        bot.send_message(message.chat.id, res, parse_mode='HTML', disable_web_page_preview=True)
    except:
        bot.send_message(message.chat.id, "❌ Ошибка формата!")

# Экспорт приложения для Vercel
app = app



