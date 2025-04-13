# Телеграм-бот знайомств "Знайома"
# Мінімально робоча структура з підтримкою анкет, лайків, чатів, преміум, рефералів та мультимовного інтерфейсу

import logging
import asyncio
import sqlite3
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import ApplicationBuilder

API_TOKEN = '7551679965:AAGkmdzrdq_U5ALWFEaThVQwXjGf07RuzNw'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Підключення до бази даних
conn = sqlite3.connect('znaioma.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    city TEXT,
    gender TEXT,
    photo_id TEXT,
    about TEXT,
    premium INTEGER DEFAULT 0,
    referral_code TEXT,
    invited_by INTEGER,
    language TEXT,
    like_count INTEGER DEFAULT 0,
    last_like_time TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS likes (
    liker_id INTEGER,
    liked_id INTEGER,
    is_match INTEGER DEFAULT 0
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
    inviter_id INTEGER,
    invited_id INTEGER
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS chats (
    user1_id INTEGER,
    user2_id INTEGER
)''')

conn.commit()

# Стан для створення анкети
class ProfileState(StatesGroup):
    name = State()
    age = State()
    city = State()
    gender = State()
    photo = State()
    about = State()

# Словник мов
languages = {
    'uk': {
        'start': "Вітаємо у боті знайомств 'Знайома'!",
        'choose_lang': "Оберіть мову / Choose language / Выберите язык:",
        'menu': "Головне меню",
    },
    'ru': {
        'start': "Добро пожаловать в бота знакомств 'Знайома'!",
        'choose_lang': "Выберите язык / Choose language / Оберіть мову:",
        'menu': "Главное меню",
    },
    'en': {
        'start': "Welcome to the dating bot 'Znaioma'!",
        'choose_lang': "Choose language / Выберите язык / Оберіть мову:",
        'menu': "Main menu",
    }
}

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Українська", "Русский", "English")
    await message.answer("Оберіть мову / Choose language / Выберите язык:", reply_markup=markup)

@dp.message_handler(lambda message: message.text in ["Українська", "Русский", "English"])
async def set_language(message: types.Message, state: FSMContext):
    lang_map = {"Українська": "uk", "Русский": "ru", "English": "en"}
    lang = lang_map[message.text]
    cursor.execute("INSERT OR IGNORE INTO users (user_id, language) VALUES (?, ?)", (message.from_user.id, lang))
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, message.from_user.id))
    conn.commit()
    await message.answer(languages[lang]['start'], reply_markup=types.ReplyKeyboardRemove())
    await message.answer("/profile - створити анкету\n/like - переглянути анкети\n/premium - преміум\n/help - допомога")

# Інші хендлери: анкета, перегляд, лайки, чат, преміум, реферали — будуть додані поетапно

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

