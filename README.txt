ІНСТРУКЦІЯ ДО БОТА «ЗНАЙОМСТВА-UA»

1. Створи бота через @BotFather у Telegram — збережи отриманий токен.
2. Встанови Python (https://www.python.org/downloads/)
3. У терміналі виконай:
   pip install -r requirements.txt
4. У файлі main.py заміни:
   ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE")
   на свій токен
5. Запусти бота командою:
   python main.py