import os
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Ottieni il token dalla variabile d'ambiente
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("Il token non è stato trovato. Controlla le variabili d'ambiente.")

# ID del canale (deve essere inserito come valore numerico, incluso il prefisso negativo)
CHANNEL_ID = -1002416787706

# Funzione per gestire il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Crea un nuovo link di invito valido per una persona
        chat_invite_link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,  # Limita il link a un solo utilizzo
        )
        # Invia il link all'utente
        await update.message.reply_text(
            f"Ecco il link per entrare nel canale 'Executed Ban':\n{chat_invite_link.invite_link}"
        )
    except Exception as e:
        # Gestisce eventuali errori
        await update.message.reply_text("Si è verificato un errore durante la creazione del link.")
        print(f"Errore: {e}")

# Configurazione del bot
app = ApplicationBuilder().token(bot_token).build()

# Aggiungi il gestore per il comando /start
app.add_handler(CommandHandler("start", start))

# Avvia il bot
if __name__ == "__main__":
    print("Bot in esecuzione...")
    app.run_polling()
