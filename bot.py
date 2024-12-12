import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Ottieni il token dalla variabile d'ambiente
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("Il token non è stato trovato. Controlla le variabili d'ambiente.")

# Funzione per gestire il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Benvenuto!")

# Configurazione del bot
app = ApplicationBuilder().token(bot_token).build()

# Aggiungi il gestore per il comando /start
app.add_handler(CommandHandler("start", start))

# Avvia il bot
if __name__ == "__main__":
    print("Bot in esecuzione...")
    app.run_polling()
