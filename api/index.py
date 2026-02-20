import telebot
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import urllib.parse
import os
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
REMINDER_SECRET = os.getenv('REMINDER_SECRET')

# Администраторы — только они могут управлять allowlist
ADMIN_USER_IDS = os.getenv('ADMIN_USER_IDS', '')
ADMIN_USERS = set()
if ADMIN_USER_IDS:
    ADMIN_USERS = {int(uid.strip()) for uid in ADMIN_USER_IDS.split(',') if uid.strip()}

# Allowlist: Telegram user IDs (env — резервный)
ALLOWED_USER_IDS = os.getenv('ALLOWED_USER_IDS', '')
ALLOWED_USERS_ENV = set()
if ALLOWED_USER_IDS:
    ALLOWED_USERS_ENV = {int(uid.strip()) for uid in ALLOWED_USER_IDS.split(',') if uid.strip()}

# Upstash Redis (динамический allowlist)
REDIS_URL = os.getenv('UPSTASH_REDIS_REST_URL')
REDIS_TOKEN = os.getenv('UPSTASH_REDIS_REST_TOKEN')
redis_client = None
if REDIS_URL and REDIS_TOKEN:
    from upstash_redis import Redis
    redis_client = Redis(url=REDIS_URL, token=REDIS_TOKEN)

REDIS_ALLOWLIST_KEY = 'allowed_users'

bot = telebot.TeleBot(API_TOKEN, threaded=False)
app = Flask(__name__)

# --- Утилиты ---

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{5,32}$')

# Города с IANA таймзонами (DST-aware)
CITIES = [
    ("Riga",        ZoneInfo("Europe/Riga")),
    ("Tel-Aviv",    ZoneInfo("Asia/Tel_Aviv")),
    ("Rome",        ZoneInfo("Europe/Rome")),
    ("Istanbul",    ZoneInfo("Europe/Istanbul")),
    ("Bishkek",     ZoneInfo("Asia/Bishkek")),
    ("Beijing",     ZoneInfo("Asia/Shanghai")),
    ("Los Angeles", ZoneInfo("America/Los_Angeles")),
]

# Хранилище последнего QStash message ID (в памяти, per-instance)
last_qstash_msg = {}

def is_valid_username(username):
    """Валидация Telegram username."""
    return bool(USERNAME_RE.match(username))

def parse_usernames(text):
    """Парсинг нескольких @username из строки. Возвращает список валидных."""
    raw = [u.lstrip('@').strip() for u in text.split() if u.strip()]
    return [u for u in raw if is_valid_username(u)]

def get_redis_allowed_users():
    """Получить allowlist из Redis. Возвращает set или None при ошибке."""
    if not redis_client:
        return None
    try:
        members = redis_client.smembers(REDIS_ALLOWLIST_KEY)
        if members:
            return {int(uid) for uid in members}
        return set()
    except Exception as e:
        print(f"Redis read error: {e}")
        return None

def is_user_allowed(user_id):
    """Проверка allowlist: Redis → env fallback. Пустой список = доступ всем."""
    # Сначала проверяем Redis
    redis_users = get_redis_allowed_users()
    if redis_users is not None:
        if not redis_users:  # Redis есть, но список пуст
            # Fallback на env если Redis пуст
            if not ALLOWED_USERS_ENV:
                return True
            return user_id in ALLOWED_USERS_ENV
        return user_id in redis_users
    # Redis недоступен — fallback на env
    if not ALLOWED_USERS_ENV:
        return True
    return user_id in ALLOWED_USERS_ENV

def is_admin(user_id):
    """Проверка прав админа. Админы указаны в ADMIN_USER_IDS."""
    return user_id in ADMIN_USERS

def cancel_qstash_message(msg_id):
    """Отменить QStash сообщение по ID. Возвращает True если успешно."""
    try:
        conn = http.client.HTTPSConnection("qstash.upstash.io", timeout=10)
        conn.request("DELETE", f"/v2/messages/{msg_id}", headers={
            "Authorization": f"Bearer {QSTASH_TOKEN}"
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return 200 <= resp.status < 300
    except Exception as e:
        print(f"Cancel error: {e}")
        return False

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
async def send_userbot_messages(usernames, text):
    """Отправка ЛС нескольким пользователям за одно подключение."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(TELETHON_SESSION), int(TG_API_ID), TG_API_HASH)
    await client.connect()
    results = {}
    try:
        for username in usernames:
            try:
                await client.send_message(username, text)
                results[username] = True
            except Exception as e:
                print(f"Telethon error for user: {e}")
                results[username] = False
    finally:
        await client.disconnect()
    return results

# Вход для будильника (QStash)
@app.route('/reminder', methods=['POST'])
def reminder_trigger():
    # Проверка секрета — только QStash знает этот токен
    if REMINDER_SECRET:
        if request.headers.get('X-Reminder-Secret', '') != REMINDER_SECRET:
            return 'Forbidden', 403

    try:
        data = request.json
        chat_id = data.get('chat_id')
        zoom = data.get('zoom', '')
        target_usernames = data.get('target_usernames', [])
        title = data.get('title', 'Встреча')

        # Тип напоминания
        reminder_type = data.get('type', 'main')

        # Экранирование для HTML
        safe_zoom = escape(zoom)
        safe_title = escape(title)

        if reminder_type == 'urgent':
            # Срочное напоминание за 5 минут
            bot.send_message(chat_id, 
                f"⚠️ <b>{safe_title}</b> через 5 минут!\n{safe_zoom}", 
                parse_mode='HTML', disable_web_page_preview=True)

            # Личные сообщения участникам через userbot
            valid_usernames = [u for u in target_usernames if is_valid_username(u)]
            if valid_usernames and TELETHON_SESSION and TG_API_ID and TG_API_HASH:
                msg = f"⚠️ Через 5 минут!\n\n📌 {safe_title}\n🔗 {zoom}"
                try:
                    results = asyncio.run(send_userbot_messages(valid_usernames, msg))
                    sent = [u for u, ok in results.items() if ok]
                    failed = [u for u, ok in results.items() if not ok]
                    if sent:
                        mentions = ", ".join(f"@{escape(u)}" for u in sent)
                        bot.send_message(chat_id, f"✅ Срочное ЛС отправлено: {mentions}", parse_mode='HTML')
                    if failed:
                        mentions = ", ".join(f"@{escape(u)}" for u in failed)
                        bot.send_message(chat_id, f"⚠️ Не удалось отправить: {mentions}", parse_mode='HTML')
                except Exception as e:
                    print(f"Telethon urgent error: {e}")
                    bot.send_message(chat_id, "⚠️ Не удалось отправить срочные ЛС")

            return 'OK', 200

        # Основное напоминание за 45 минут
        bot.send_message(chat_id, 
            f"⚡️ Напоминаю: <b>{safe_title}</b>\n<b>ZOOM через 40 минут</b>\n{safe_zoom}", 
            parse_mode='HTML', disable_web_page_preview=True)

        # Личные сообщения участникам через userbot
        valid_usernames = [u for u in target_usernames if is_valid_username(u)]
        if valid_usernames and TELETHON_SESSION and TG_API_ID and TG_API_HASH:
            safe_title = escape(title)
            msg = f"👋 Привет! Напоминаю о встрече:\n\n📌 {safe_title}\n🔗 {zoom}\n\n⏰ Через ~40 минут"
            try:
                results = asyncio.run(send_userbot_messages(valid_usernames, msg))
                sent = [u for u, ok in results.items() if ok]
                failed = [u for u, ok in results.items() if not ok]
                if sent:
                    mentions = ", ".join(f"@{escape(u)}" for u in sent)
                    bot.send_message(chat_id, f"✅ ЛС отправлено: {mentions}", parse_mode='HTML')
                if failed:
                    mentions = ", ".join(f"@{escape(u)}" for u in failed)
                    bot.send_message(chat_id, f"⚠️ Не удалось отправить: {mentions}", parse_mode='HTML')
            except Exception as e:
                print(f"Telethon error: {e}")
                bot.send_message(chat_id, "⚠️ Не удалось отправить личные напоминания")
        elif valid_usernames:
            print("Telethon not configured, cannot send DMs")
    except Exception as e:
        print(f"Reminder error: {e}")
    return 'OK', 200

@bot.message_handler(commands=['start'])
def start(message):
    if not is_user_allowed(message.from_user.id):
        return
    bot.send_message(message.chat.id,
        "Бот готов! Пришли:\n"
        "<code>Тема, ДД.ММ.ГГГГ, ЧЧ:ММ, Ссылка, @user1 @user2</code>\n\n"
        "@username — необязательно (можно несколько через пробел)\n"
        "/cancel — отменить последнее напоминание\n"
        "/adduser ID — добавить пользователя\n"
        "/removeuser ID — удалить пользователя\n"
        "/users — список пользователей",
        parse_mode='HTML')

@bot.message_handler(commands=['adduser'])
def add_user(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ Только для админов")
        return
    if not redis_client:
        bot.send_message(message.chat.id, "⚠️ Redis не настроен")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /adduser <ID>\nID можно узнать у @userinfobot")
        return
    try:
        user_id = int(parts[1])
        redis_client.sadd(REDIS_ALLOWLIST_KEY, str(user_id))
        bot.send_message(message.chat.id, f"✅ Пользователь <code>{user_id}</code> добавлен", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID должен быть числом")

@bot.message_handler(commands=['removeuser'])
def remove_user(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ Только для админов")
        return
    if not redis_client:
        bot.send_message(message.chat.id, "⚠️ Redis не настроен")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /removeuser <ID>")
        return
    try:
        user_id = int(parts[1])
        # Нельзя удалить самого себя
        if user_id == message.from_user.id:
            bot.send_message(message.chat.id, "❌ Нельзя удалить себя")
            return
        redis_client.srem(REDIS_ALLOWLIST_KEY, str(user_id))
        bot.send_message(message.chat.id, f"✅ Пользователь <code>{user_id}</code> удалён", parse_mode='HTML')
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID должен быть числом")

@bot.message_handler(commands=['users'])
def list_users(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ Только для админов")
        return
    if not redis_client:
        bot.send_message(message.chat.id, "⚠️ Redis не настроен")
        return
    try:
        members = redis_client.smembers(REDIS_ALLOWLIST_KEY)
        if members:
            user_list = "\n".join(f"• <code>{uid}</code>" for uid in sorted(members))
            bot.send_message(message.chat.id, f"👥 Разрешённые пользователи:\n{user_list}", parse_mode='HTML')
        else:
            env_info = ""
            if ALLOWED_USERS_ENV:
                env_list = ", ".join(str(uid) for uid in ALLOWED_USERS_ENV)
                env_info = f"\n\n📋 Из env: {env_list}"
            bot.send_message(message.chat.id, f"📋 Список в Redis пуст (доступ через env){env_info}")
    except Exception as e:
        print(f"Redis list error: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка чтения Redis")

@bot.message_handler(commands=['cancel'])
def cancel_reminder(message):
    if not is_user_allowed(message.from_user.id):
        return
    chat_id = message.chat.id
    msg_id = last_qstash_msg.get(chat_id)
    if not msg_id:
        bot.send_message(chat_id, "❌ Нет активных напоминаний для отмены")
        return
    if cancel_qstash_message(msg_id):
        del last_qstash_msg[chat_id]
        bot.send_message(chat_id, "✅ Напоминание отменено")
    else:
        bot.send_message(chat_id, "⚠️ Не удалось отменить (возможно, уже отправлено)")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel:'))
def cancel_callback(call):
    if not is_user_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Нет доступа")
        return
    qstash_id = call.data.split(':', 1)[1]
    if cancel_qstash_message(qstash_id):
        bot.answer_callback_query(call.id, "✅ Напоминание отменено")
        # Убираем кнопку отмены, оставляем только календарь
        if call.message and call.message.reply_markup:
            new_kb = telebot.types.InlineKeyboardMarkup()
            for row in call.message.reply_markup.keyboard:
                for btn in row:
                    if btn.url:  # оставляем URL-кнопки (календарь)
                        new_kb.add(btn)
            cancelled_btn = telebot.types.InlineKeyboardButton("✅ Отменено", callback_data="noop")
            new_kb.add(cancelled_btn)
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=new_kb)
    else:
        bot.answer_callback_query(call.id, "⚠️ Не удалось отменить")

@bot.callback_query_handler(func=lambda call: call.data == 'noop')
def noop_callback(call):
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: True)
def create_meeting(message):
    if not is_user_allowed(message.from_user.id):
        return

    try:
        parts = [p.strip() for p in message.text.split(',')]
        if len(parts) < 4: raise ValueError
        title, date_val, time_val, zoom = parts[:4]
        
        # Парсинг нескольких @username (через пробел)
        target_usernames = []
        if len(parts) >= 5 and parts[4].strip():
            target_usernames = parse_usernames(parts[4])
            invalid = [u.lstrip('@').strip() for u in parts[4].split() if u.lstrip('@').strip() and not is_valid_username(u.lstrip('@').strip())]
            if invalid:
                bot.send_message(message.chat.id, f"❌ Некорректные @username: {', '.join(invalid)} (допустимы: буквы, цифры, _, длина 5–32)")
                return

        # Логика времени — Istanbul (DST-aware)
        ist_tz = ZoneInfo("Europe/Istanbul")
        naive_dt = datetime.strptime(f"{date_val} {time_val}", "%d.%m.%Y %H:%M")
        meeting_dt_ist = naive_dt.replace(tzinfo=ist_tz)
        now_ist = datetime.now(ist_tz)

        # Форматирование
        months = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
        days_short = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
        date_text = f"{meeting_dt_ist.day} {months[meeting_dt_ist.month-1]} {meeting_dt_ist.year}"
        day_name = days_short[meeting_dt_ist.weekday()]

        # Расчет городов (DST-aware через zoneinfo)
        meeting_utc = meeting_dt_ist.astimezone(timezone.utc)
        city_parts = []
        for city_name, city_tz in CITIES:
            city_time = meeting_utc.astimezone(city_tz)
            city_parts.append(f"{city_time.strftime('%H:%M')} {city_name}")
        # Группировка: Riga;Tel-Aviv если совпадают
        if city_parts[0].split()[0] == city_parts[1].split()[0]:
            merged = f"{city_parts[0]};{CITIES[1][0]}"
            cities = " / ".join([merged] + city_parts[2:])
        else:
            cities = " / ".join(city_parts)

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
               f"<b>ZOOM</b> — {safe_zoom}")
        if target_usernames:
            mentions = ", ".join(f"@{escape(u)}" for u in target_usernames)
            res += f"\n👥 Участники: {mentions}"

        # Inline-кнопки (календарь всегда, отмена добавится после QStash)
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("📲 Добавить в календарь", url=gcal))

        sent_msg = bot.send_message(message.chat.id, res, parse_mode='HTML',
                                    disable_web_page_preview=True, reply_markup=kb)

        # Будильник QStash (45 мин + 5 мин до встречи)
        try:
            if QSTASH_TOKEN and APP_HOST:
                clean_host = APP_HOST.replace("https://", "").replace("http://", "").rstrip("/")
                qstash_path = f"/v2/publish/https://{clean_host}/reminder"
                
                base_payload = {"chat_id": message.chat.id, "zoom": zoom, "title": title}
                if target_usernames:
                    base_payload["target_usernames"] = target_usernames

                def publish_qstash(delay_sec, extra_payload=None):
                    """Отправить одно сообщение в QStash."""
                    payload = {**base_payload, **(extra_payload or {})}
                    headers = {
                        "Authorization": f"Bearer {QSTASH_TOKEN}",
                        "Content-Type": "application/json",
                        "Upstash-Delay": f"{delay_sec}s",
                    }
                    if REMINDER_SECRET:
                        headers["Upstash-Forward-X-Reminder-Secret"] = REMINDER_SECRET
                    conn = http.client.HTTPSConnection("qstash.upstash.io", timeout=10)
                    conn.request("POST", qstash_path, body=json.dumps(payload), headers=headers)
                    resp = conn.getresponse()
                    resp_body = resp.read().decode()
                    conn.close()
                    print(f"QStash [{extra_payload.get('type','main') if extra_payload else 'main'}]: {resp.status} {resp_body}")
                    return resp.status, resp_body

                max_delay = 604800  # QStash free: макс 7 дней

                # Напоминание за 45 минут (основное + Telethon ЛС)
                reminder_time = meeting_dt_ist - timedelta(minutes=45)
                delay_45 = int((reminder_time - now_ist).total_seconds())

                if delay_45 > max_delay:
                    days = delay_45 // 86400
                    bot.send_message(message.chat.id, f"⏳ Напоминание не установлено — встреча дальше 7 дней (через {days} дн.)")
                elif delay_45 > 0:
                    status, body = publish_qstash(delay_45)
                    if 200 <= status < 300:
                        qstash_msg_id = None
                        try:
                            qstash_msg_id = json.loads(body).get('messageId')
                            if qstash_msg_id:
                                last_qstash_msg[message.chat.id] = qstash_msg_id
                        except Exception:
                            pass
                        
                        remind_text = f"🔔 Напомню в {reminder_time.strftime('%H:%M')} Ist"
                        if target_usernames:
                            mentions = ", ".join(f"@{escape(u)}" for u in target_usernames)
                            remind_text += f" (+ напишу {mentions})"
                        
                        remind_kb = None
                        if qstash_msg_id:
                            remind_kb = telebot.types.InlineKeyboardMarkup()
                            remind_kb.add(telebot.types.InlineKeyboardButton("❌ Отменить напоминание", callback_data=f"cancel:{qstash_msg_id}"))
                        bot.send_message(message.chat.id, remind_text, parse_mode='HTML', reply_markup=remind_kb)
                    else:
                        bot.send_message(message.chat.id, f"⚠️ QStash {status}: {body[:300]}")

                # Срочное напоминание за 5 минут
                delay_5 = int((meeting_dt_ist - timedelta(minutes=5) - now_ist).total_seconds())
                if 0 < delay_5 <= max_delay:
                    publish_qstash(delay_5, {"type": "urgent"})
        except Exception as e:
            print(f"QStash error: {e}")
            bot.send_message(message.chat.id, f"⚠️ Не удалось установить напоминание\n<code>{escape(str(e))}</code>", parse_mode='HTML')

    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка формата! Пришли: Тема, ДД.ММ.ГГГГ, ЧЧ:ММ, Ссылка, @user1 @user2")

