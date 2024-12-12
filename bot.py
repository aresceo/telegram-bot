import os
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.ext import MessageHandler, filters
import logging

# Configura il logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Ottieni il token dalla variabile d'ambiente
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("Il token non è stato trovato. Controlla le variabili d'ambiente.")

# ID del canale (deve essere numerico, incluso il prefisso negativo)
CHANNEL_ID = -1002297768070

# Lista di utenti in attesa di approvazione
pending_approval = {}

# Funzione per gestire il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    
    try:
        # Crea un nuovo link di invito valido per una sola persona
        chat_invite_link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,  # Limita il link a un solo utilizzo
        )
        
        # Aggiungi l'utente alla lista di approvazione
        pending_approval[user_id] = chat_invite_link.invite_link
        
        # Invia il messaggio di attesa
        await update.message.reply_text(
            f"Sei stato aggiunto alla lista di attesa per entrare nel canale 'Executed Ban'. "
            "Un amministratore dovrà approvarti. Ti invierò il link appena approvato."
        )
        
        # Notifica l'amministratore (puoi sostituire con il tuo ID Telegram)
        admin_id = 7839114402  # Sostituisci con l'ID dell'amministratore
        await context.bot.send_message(
            admin_id,
            f"Nuova richiesta di accesso al canale da {username} (ID: {user_id})."
            " Approva o rifiuta questa richiesta."
        )
    
    except Exception as e:
        # Gestisce eventuali errori
        await update.message.reply_text("Si è verificato un errore durante la creazione del link.")
        logger.error(f"Errore: {e}")

# Funzione per gestire l'approvazione
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = int(context.args[0])  # ID dell'utente da approvare
    action = context.args[1].lower()  # "approve" o "deny"

    if action not in ["approve", "deny"]:
        await update.message.reply_text("Azione non valida. Usa /approve <user_id> approve o deny.")
        return

    if user_id not in pending_approval:
        await update.message.reply_text("Questo utente non è in lista di attesa.")
        return

    chat_invite_link = pending_approval[user_id]

    if action == "approve":
        # Invia il link di invito all'utente
        await context.bot.send_message(
            user_id,
            f"Il tuo accesso al canale 'Executed Ban' è stato approvato. Ecco il link per entrare: {chat_invite_link}"
        )
        await update.message.reply_text(f"Utente {user_id} approvato e link inviato.")
    else:
        # Se rifiutato, informiamo l'utente
        await context.bot.send_message(
            user_id,
            "La tua richiesta di accesso al canale 'Executed Ban' è stata rifiutata."
        )
        await update.message.reply_text(f"Utente {user_id} rifiutato.")
    
    # Rimuovi l'utente dalla lista di approvazione
    del pending_approval[user_id]

# Configurazione del bot
app = ApplicationBuilder().token(bot_token).build()

# Aggiungi il gestore per il comando /start
app.add_handler(CommandHandler("start", start))

# Aggiungi il gestore per l'approvazione
app.add_handler(CommandHandler("approve", approve))

# Avvia il bot
if __name__ == "__main__":
    print("Bot in esecuzione...")
    app.run_polling()
