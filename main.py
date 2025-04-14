import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler, ConversationHandler
import sqlite3

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for ConversationHandler
NAME, AGE, GENDER, CITY, LOOKING_FOR, PHOTO = range(6)

# Connect to SQLite
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

# Start command
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Привіт! Я бот знайомств 'Знайомства-UA'. Давай створимо твою анкету! Як тебе звати?")
    return NAME

def name(update: Update, context: CallbackContext):
    context.user_data['name'] = update.message.text
    update.message.reply_text("Скільки тобі років?")
    return AGE

def age(update: Update, context: CallbackContext):
    context.user_data['age'] = int(update.message.text)
    update.message.reply_text("Яка твоя стать? (чоловік / жінка)")
    return GENDER

def gender(update: Update, context: CallbackContext):
    context.user_data['gender'] = update.message.text.lower()
    update.message.reply_text("З якого ти міста?")
    return CITY

def city(update: Update, context: CallbackContext):
    context.user_data['city'] = update.message.text
    update.message.reply_text("Кого шукаєш? (чоловіка / жінку)")
    return LOOKING_FOR

def looking_for(update: Update, context: CallbackContext):
    context.user_data['looking_for'] = update.message.text.lower()
    update.message.reply_text("Надішли своє фото для анкети")
    return PHOTO

def photo(update: Update, context: CallbackContext):
    photo_file = update.message.photo[-1].file_id
    user_id = update.message.from_user.id

    # Збереження в базу даних
    c.execute('REPLACE INTO users (user_id, name, age, gender, city, looking_for, photo) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (user_id,
               context.user_data['name'],
               context.user_data['age'],
               context.user_data['gender'],
               context.user_data['city'],
               context.user_data['looking_for'],
               photo_file))
    conn.commit()

    update.message.reply_text("Анкету створено! Можеш переглядати інших користувачів за командою /search")
    return ConversationHandler.END

def search(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    c.execute("SELECT gender, looking_for FROM users WHERE user_id=?", (user_id,))
    current = c.fetchone()
    if not current:
        update.message.reply_text("Спочатку зареєструйся за допомогою /start")
        return
    gender, looking_for = current
    
    # Отримати анкету іншої статі
    c.execute("SELECT * FROM users WHERE gender=? AND user_id!=? AND user_id NOT IN (SELECT liked_id FROM likes WHERE liker_id=?) LIMIT 1", (looking_for, user_id, user_id))
    person = c.fetchone()
    if not person:
        update.message.reply_text("Немає нових анкет наразі. Спробуй пізніше!")
        return

    buttons = [
        [InlineKeyboardButton("Цікаво", callback_data=f"like_{person[0]}"), InlineKeyboardButton("Пропустити", callback_data="skip")]
    ]
    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=person[6],
        caption=f"Ім’я: {person[1]}\nВік: {person[2]}\nМісто: {person[4]}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if query.data.startswith("like_"):
        liked_id = int(query.data.split("_")[1])
        c.execute("INSERT INTO likes (liker_id, liked_id) VALUES (?, ?)", (user_id, liked_id))
        conn.commit()

        # Чи є взаємність
        c.execute("SELECT * FROM likes WHERE liker_id=? AND liked_id=?", (liked_id, user_id))
        if c.fetchone():
            context.bot.send_message(user_id, "У вас взаємна симпатія! Ви можете поспілкуватися: @" + context.bot.get_chat(liked_id).username)
            context.bot.send_message(liked_id, "У вас взаємна симпатія! Ви можете поспілкуватися: @" + context.bot.get_chat(user_id).username)
        query.edit_message_reply_markup(reply_markup=None)
        query.message.reply_text("Симпатія зафіксована. Хочеш ще — напиши /search")

    elif query.data == "skip":
        query.edit_message_reply_markup(reply_markup=None)
        query.message.reply_text("Наступна анкета — /search")

# Command to show profile
def profile(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    data = c.fetchone()
    if data:
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=data[6],
            caption=f"Твоя анкета:\nІм’я: {data[1]}\nВік: {data[2]}\nСтать: {data[3]}\nМісто: {data[4]}\nШукаєш: {data[5]}"
        )
    else:
        update.message.reply_text("Анкету не знайдено. Створи її командою /start")

# Main function
def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()

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

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()

if __name__ == '__main__':
    main()