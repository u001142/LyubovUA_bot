import logging
import os
import sqlite3
import math
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from fastapi import FastAPI, Request
import uvicorn
import nest_asyncio

# === ЛОГУВАННЯ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === СТАНИ АНКЕТИ ===
NAME, AGE, GENDER, LOCATION, CITY, LOOKING_FOR, PHOTO = range(7)

# === БАЗА ДАНИХ ===
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT, age INTEGER, gender TEXT,
    lat REAL, lon REAL,
    city TEXT,
    looking_for TEXT, photo TEXT,
    premium INTEGER DEFAULT 0, banned INTEGER DEFAULT 0
)""")
c.execute("CREATE TABLE IF NOT EXISTS likes (liker_id INTEGER, liked_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS chats (user1 INTEGER, user2 INTEGER)")
c.execute("CREATE TABLE IF NOT EXISTS referrals (referrer_id INTEGER, invited_id INTEGER UNIQUE)")
conn.commit()

# === Haversine ===
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# === БІЗНЕС-ЛОГІКА ===
# (Тут розміщуються всі функції: start, name, age, gender, city, looking_for, photo,
#  profile, search, button, relay, premium, handle_text_buttons — без змін з вашого коду)

# ПРИКЛАД: handler для текстових кнопок
async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔍 Пошук":
        await search(update, context)
    elif text == "👤 Профіль":
        await profile(update, context)
    elif text == "💎 Преміум":
        await premium(update, context)

# === TELEGRAM APP ===
app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
        AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age)],
        GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender)],
        CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city)],
        LOOKING_FOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, looking_for)],
        PHOTO: [MessageHandler(filters.PHOTO, photo)],
    },
    fallbacks=[]
)

app.add_handler(conv_handler)
app.add_handler(CommandHandler("search", search))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(CommandHandler("premium", premium))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
app.add_handler(MessageHandler(filters.PHOTO, relay))

# === FASTAPI WEBHOOK ===
web_app = FastAPI()

@web_app.post("/webhook")
async def process_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return {"ok": True}

async def setup():
    webhook_url = "https://lyubovua-bot.onrender.com/webhook"
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_webhook(webhook_url)

if __name__ == "__main__":
    nest_asyncio.apply()
    import asyncio
    asyncio.get_event_loop().run_until_complete(setup())
    uvicorn.run("main:web_app", host="0.0.0.0", port=10000)
