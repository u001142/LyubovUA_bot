import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler, ContextTypes
)
import sqlite3
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
print("WEBHOOK_SECRET:", WEBHOOK_SECRET)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI
app = FastAPI()

# Telegram Application
application = Application.builder().token(TOKEN).build()

# Ініціалізація при запуску FastAPI
@app.on_event("startup")
async def on_startup():
    await application.initialize()

# SQLite
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    gender TEXT,
    city TEXT,
    looking_for TEXT,
    photo TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS likes (
    liker_id INTEGER,
    liked_id INTEGER,
    matched INTEGER DEFAULT 0
)''')
conn.commit()

# Conversation states
NAME, AGE, GENDER, CITY, LOOKING_FOR, PHOTO = range(6)

# Хендлери
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Я бот знайомств 'Знайомства-UA'. Давай створимо твою анкету! Як тебе звати?")
    return NAME

async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Скільки тобі років?")
    return AGE

async def age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = int(update.message.text)
    await update.message.reply_text("Яка твоя стать? (чоловік / жінка)")
    return GENDER

async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text.lower()
    await update.message.reply_text("З якого ти міста?")
    return CITY

async def city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['city'] = update.message.text
    await update.message.reply_text("Кого шукаєш? (чоловіка / жінку)")
    return LOOKING_FOR

async def looking_for(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['looking_for'] = update.message.text.lower()
    await update.message.reply_text("Надішли своє фото для анкети")
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = update.message.photo[-1].file_id
    user_id = update.message.from_user.id
    c.execute('REPLACE INTO users (user_id, name, age, gender, city, looking_for, photo) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (user_id, context.user_data['name'], context.user_data['age'],
               context.user_data['gender'], context.user_data['city'],
               context.user_data['looking_for'], photo_file))
    conn.commit()
    await update.message.reply_text("Анкету створено! Можеш переглядати інших користувачів за командою /search")
    return ConversationHandler.END

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    c.execute("SELECT gender, looking_for FROM users WHERE user_id=?", (user_id,))
    current = c.fetchone()
    if not current:
        await update.message.reply_text("Спочатку зареєструйся за допомогою /start")
        return
    gender, looking_for = current
    c.execute("SELECT * FROM users WHERE gender=? AND user_id!=? AND user_id NOT IN (SELECT liked_id FROM likes WHERE liker_id=?) LIMIT 1",
              (looking_for, user_id, user_id))
    person = c.fetchone()
    if not person:
        await update.message.reply_text("Немає нових анкет наразі. Спробуй пізніше!")
        return
    buttons = [[InlineKeyboardButton("Цікаво", callback_data=f"like_{person[0]}"),
                InlineKeyboardButton("Пропустити", callback_data="skip")]]
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=person[6],
        caption=f"Ім’я: {person[1]}\nВік: {person[2]}\nМісто: {person[4]}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data.startswith("like_"):
        liked_id = int(query.data.split("_")[1])
        c.execute("INSERT INTO likes (liker_id, liked_id) VALUES (?, ?)", (user_id, liked_id))
        conn.commit()
        c.execute("SELECT * FROM likes WHERE liker_id=? AND liked_id=?", (liked_id, user_id))
        if c.fetchone():
            await context.bot.send_message(user_id, "У вас взаємна симпатія!")
            await context.bot.send_message(liked_id, "У вас взаємна симпатія!")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Симпатія зафіксована. Хочеш ще — напиши /search")
    elif query.data == "skip":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Наступна анкета — /search")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    data = c.fetchone()
    if data:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=data[6],
            caption=f"Твоя анкета:\nІм’я: {data[1]}\nВік: {data[2]}\nСтать: {data[3]}\nМісто: {data[4]}\nШукаєш: {data[5]}"
        )
    else:
        await update.message.reply_text("Анкету не знайдено. Створи її командою /start")

# Хендлери
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
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

application.add_handler(conv_handler)
application.add_handler(CommandHandler("search", search))
application.add_handler(CommandHandler("profile", profile))
application.add_handler(CallbackQueryHandler(button))

# FastAPI endpoint для Webhook
@app.post(f"/{WEBHOOK_SECRET}")
async def telegram_webhook(req: Request):
    print("Webhook triggered!")
    data = await req.json()
    print("Raw update data:", data)
    update = Update.de_json(data, application.bot)
    print("Parsed update:", update)
    await application.process_update(update)
    return {"ok": True}
