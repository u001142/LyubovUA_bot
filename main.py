from fastapi import FastAPI, Request from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler import os, json, asyncio, random

app = FastAPI() TOKEN = os.getenv("BOT_TOKEN") WEBHOOK_PATH = "/webhook" BOT_URL = os.getenv("BOT_URL")  # e.g., https://your-bot.onrender.com

application = Application.builder().token(TOKEN).build()

users = {}  # user_id: {profile data} likes = {}  # user_id: set(user_ids they liked) liked_by = {}  # user_id: set(user_ids who liked them) lang_pref = {}  # user_id: language code pending_profiles = {}  # user_id: next profile to show

premium_users = set() referrals = {}

LANGUAGES = { 'uk': 'Українська', 'ru': 'Русский', 'en': 'English' }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): keyboard = [[KeyboardButton(text=lang)] for lang in LANGUAGES.values()] await update.message.reply_text("Оберіть мову / Choose your language:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE): lang_value = update.message.text lang_code = next((code for code, name in LANGUAGES.items() if name == lang_value), None) if lang_code: user_id = update.message.from_user.id users.setdefault(user_id, {})['lang'] = lang_code context.user_data['step'] = 'name' await update.message.reply_text("Мову обрано! Надішліть своє ім’я:") elif context.user_data.get('step'): await collect_profile(update, context) else: await update.message.reply_text("Будь ласка, скористайтеся командою /start")

async def collect_profile(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.message.from_user.id text = update.message.text step = context.user_data.get('step') profile = users.setdefault(user_id, {})

if step == 'name':
    profile['name'] = text
    context.user_data['step'] = 'age'
    await update.message.reply_text("Скільки вам років?")
elif step == 'age':
    profile['age'] = text
    context.user_data['step'] = 'city'
    await update.message.reply_text("Місто:")
elif step == 'city':
    profile['city'] = text
    context.user_data['step'] = 'gender'
    await update.message.reply_text("Ваша стать (ч/ж):")
elif step == 'gender':
    profile['gender'] = text
    context.user_data['step'] = 'photo'
    await update.message.reply_text("Надішліть своє фото:")
elif update.message.photo:
    file_id = update.message.photo[-1].file_id
    profile['photo'] = file_id
    context.user_data['step'] = 'about'
    await update.message.reply_text("Розкажіть про себе або натисніть /done")
elif step == 'about':
    profile['about'] = text
    await update.message.reply_text("Анкету створено! Використовуйте /like для перегляду анкет")
    context.user_data['step'] = None

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data['step'] = None await update.message.reply_text("Анкету завершено. Скористайтесь /like для перегляду інших анкет.")

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.message.from_user.id user_profile = users.get(user_id) if not user_profile: await update.message.reply_text("Спочатку створіть анкету через /start") return

other_ids = list(users.keys())
random.shuffle(other_ids)
for other_id in other_ids:
    if other_id == user_id:
        continue
    if other_id in likes.get(user_id, set()):
        continue
    pending_profiles[user_id] = other_id
    other_profile = users[other_id]
    buttons = [[
        InlineKeyboardButton("Вподобати", callback_data="like"),
        InlineKeyboardButton("Пропустити", callback_data="skip")
    ]]
    markup = InlineKeyboardMarkup(buttons)
    await context.bot.send_photo(chat_id=user_id, photo=other_profile['photo'], caption=f"{other_profile['name']}, {other_profile['age']}, {other_profile['city']}\n{other_profile.get('about', '')}", reply_markup=markup)
    return
await update.message.reply_text("Анкет більше немає.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer() user_id = query.from_user.id other_id = pending_profiles.get(user_id)

if not other_id:
    await query.edit_message_caption(caption="Щось пішло не так.")
    return

if query.data == "like":
    likes.setdefault(user_id, set()).add(other_id)
    liked_by.setdefault(other_id, set()).add(user_id)
    if user_id in likes.get(other_id, set()):
        # Взаємна симпатія
        await context.bot.send_message(chat_id=other_id, text=f"У вас взаємна симпатія з {users[user_id]['name']}!")
        await context.bot.send_message(chat_id=user_id, text=f"У вас взаємна симпатія з {users[other_id]['name']}!")
    await query.edit_message_caption(caption="Вподобано!")
elif query.data == "skip":
    await query.edit_message_caption(caption="Пропущено")

Webhook

@app.post(WEBHOOK_PATH) async def webhook(req: Request): data = await req.json() update = Update.de_json(data, application.bot) await application.update_queue.put(update) return {"status": "ok"}

Команди

application.add_handler(CommandHandler("start", start)) application.add_handler(CommandHandler("done", done)) application.add_handler(CommandHandler("like", like)) application.add_handler(CallbackQueryHandler(handle_callback)) application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_language)) application.add_handler(MessageHandler(filters.ALL, collect_profile))

Установка Webhook (один раз)

async def set_webhook(): await application.bot.set_webhook(f"{BOT_URL}{WEBHOOK_PATH}")

if name == "main": import uvicorn asyncio.run(set_webhook()) uvicorn.run("main:app", host="0.0.0.0", port=10000)

