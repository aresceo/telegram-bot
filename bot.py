import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Ciao! Sono un bot Telegram.")

if __name__ == '__main__':
    bot_token = os.getenv("7897882707:AAGjonYUrDa_qmBkNbdIoAzL2jApSQJN4ug")
    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
