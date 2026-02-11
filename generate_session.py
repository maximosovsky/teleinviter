"""
Одноразовый скрипт для генерации Telethon StringSession.
Запусти локально: python generate_session.py
Скопируй полученную строку в Vercel env: TELETHON_SESSION
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = input("Введи API_ID: ")
API_HASH = input("Введи API_HASH: ")

with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
    print("\n✅ Твоя StringSession (скопируй целиком):\n")
    print(client.session.save())
