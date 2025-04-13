# === Імпорти ===
import logging
import os
import sqlite3
import math
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
import uvicorn
import nest_asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

# === Логування ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Стани анкети ===
NAME, AGE, GENDER, LOCATION, CITY, LOOKING_FOR, PHOTO = range(7)

# === База даних ===
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

# === Функції ===
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# === Хендлери ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if context.args:
        referrer_id = int(context.args[0])
        if referrer_id != user_id:
            try:
                c.execute("INSERT INTO referrals (referrer_id, invited_id) VALUES (?, ?)", (referrer_id, user_id))
                conn.commit()
            except:
                pass
            c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (referrer_id,))
            count = c.fetchone()[0]
            if count >= 5:
                c.execute("UPDATE users SET premium=1 WHERE user_id=?", (referrer_id,))
                conn.commit()
                await context.bot.send_message(referrer_id, "🎉 У тебе вже 5 запрошених — ПРЕМІУМ активовано!")
    await update.message.reply_text("Привіт! Як тебе звати?")
    return NAME

async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Скільки тобі років?")
    return AGE

async def age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❗ Введи, будь ласка, свій вік числом.")
        return AGE
    context.user_data["age"] = int(text)
    kb = ReplyKeyboardMarkup([['Чоловік', 'Жінка']], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Оберіть свою стать:", reply_markup=kb)
    return GENDER

async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gender_raw = update.message.text.strip().lower()
    context.user_data["gender"] = "жінка" if "жін" in gender_raw else "чоловік"
    await update.message.reply_text("В якому місті ти живеш?")
    return CITY

async def city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text.strip().lower()
    kb = ReplyKeyboardMarkup([['Чоловіка', 'Жінку']], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Кого шукаєш?", reply_markup=kb)
    return LOOKING_FOR

async def looking_for(update: Update, context: ContextTypes.DEFAULT_TYPE):
    looking_raw = update.message.text.strip().lower()
    context.user_data["looking_for"] = "жінка" if "жін" in looking_raw else "чоловік"
    await update.message.reply_text("Надішли своє фото:")
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    photo_id = update.message.photo[-1].file_id
    c.execute("REPLACE INTO users (user_id, name, age, gender, lat, lon, city, looking_for, photo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
        user.id,
        context.user_data["name"],
        context.user_data["age"],
        context.user_data["gender"],
        None, None,
        context.user_data["city"].capitalize(),
        context.user_data["looking_for"],
        photo_id
    ))
    conn.commit()
    kb = ReplyKeyboardMarkup([["🔍 Пошук", "👤 Профіль", "💎 Преміум"]], resize_keyboard=True)
    await update.message.reply_text("Анкету збережено. Користуйся меню нижче.", reply_markup=kb)
    return ConversationHandler.END

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = c.fetchone()
    if user:
        await context.bot.send_photo(update.effective_chat.id, photo=user[8], caption=f"{user[1]}, {user[2]} років\nМісто: {user[6]}")
    else:
        await update.message.reply_text("Анкета не знайдена. Напиши /start")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    me = c.fetchone()
    if not me:
        return await update.message.reply_text("Спочатку зареєструйся через /start")
    my_city, looking_for = me[6], me[7]
    c.execute("SELECT * FROM users WHERE gender=? AND city=? AND user_id!=?", (looking_for, my_city, uid))
    users = c.fetchall()
    for user in users:
        if user[10] == 1: continue
        c.execute("SELECT 1 FROM likes WHERE liker_id=? AND liked_id=?", (uid, user[0]))
        if c.fetchone(): continue
        buttons = [[InlineKeyboardButton("❤️ Цікаво", callback_data=f"like_{user[0]}"), InlineKeyboardButton("⛔ Скарга", callback_data=f"ban_{user[0]}")]]
        await context.bot.send_photo(update.effective_chat.id, photo=user[8], caption=f"{user[1]}, {user[2]} років\nМісто: {user[6]}", reply_markup=InlineKeyboardMarkup(buttons))
        return
    await update.message.reply_text("😔 У твоєму місті немає нових анкет або всі вже переглянуті.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if query.data.startswith("like_"):
        target = int(query.data.split("_")[1])
        c.execute("SELECT timestamp FROM likes WHERE liker_id=? AND liked_id=? ORDER BY timestamp DESC LIMIT 1", (uid, target))
        row = c.fetchone()
        if row and datetime.now() - datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") < timedelta(hours=24):
            return await query.edit_message_caption(caption="❗️Ти вже ставив(ла) лайк цьому користувачу сьогодні.")
        c.execute("INSERT INTO likes (liker_id, liked_id) VALUES (?, ?)", (uid, target))
        conn.commit()
        c.execute("SELECT * FROM likes WHERE liker_id=? AND liked_id=?", (target, uid))
        if c.fetchone():
            c.execute("INSERT INTO chats VALUES (?, ?)", (uid, target))
            conn.commit()
            await context.bot.send_message(uid, "💘 Взаємна симпатія! Ви можете спілкуватись.")
            await context.bot.send_message(target, "💘 Взаємна симпатія! Ви можете спілкуватись.")
        else:
            await context.bot.send_message(target, "❤️ Хтось зацікавився твоєю анкетою!")
        await search(update, context)
    elif query.data.startswith("ban_"):
        bad = int(query.data.split("_")[1])
        c.execute("UPDATE users SET banned=1 WHERE user_id=?", (bad,))
        conn.commit()
        await context.bot.send_message(uid, "👎 Користувача заблоковано.")
        await search(update, context)

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    c.execute("SELECT premium FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    if user and user[0] == 1:
        return await update.message.reply_text("💎 У тебе вже активний ПРЕМІУМ!")
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
    invited = c.fetchone()[0]
    link = f"https://t.me/znayomstva_krop_ua_bot?start={user_id}"
    share_button = InlineKeyboardMarkup([[InlineKeyboardButton("📲 Поділитися ботом", url=f"https://t.me/share/url?url={link}")]])
    await update.message.reply_text(f"Щоб отримати ПРЕМІУМ — запроси 5 друзів!\nЗапрошено: {invited} / 5\nЗалишилось: {5 - invited}", reply_markup=share_button, parse_mode=ParseMode.HTML)

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔍 Пошук":
        await search(update, context)
    elif text == "👤 Профіль":
        await profile(update, context)
    elif text == "💎 Преміум":
        await premium(update, context)

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    c.execute("SELECT user2 FROM chats WHERE user1=? UNION SELECT user1 FROM chats WHERE user2=?", (uid, uid))
    row = c.fetchone()
    if row:
        await context.bot.copy_message(chat_id=row[0], from_chat_id=uid, message_id=update.message.message_id)

# === Telegram App ===
app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
conv = ConversationHandler(
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
app.add_handler(conv)
app.add_handler(CommandHandler("search", search))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(CommandHandler("premium", premium))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, relay))

# === Webhook FastAPI ===
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
