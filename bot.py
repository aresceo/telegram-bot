import os
import sqlite3
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import logging

# Configura il logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Ottieni il token dalla variabile d'ambiente
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("Il token non è stato trovato. Controlla le variabili d'ambiente.")

# ID dei canali
CHANNEL_ID = -1002297768070  # Cambia con l'ID del tuo canale
GROUP_ID = -1002432052771  # Cambia con l'ID del tuo gruppo

# Connessione al database SQLite
conn = sqlite3.connect('requests.db', check_same_thread=False)
cursor = conn.cursor()

# Crea una tabella per le richieste in sospeso se non esiste
cursor.execute('''
CREATE TABLE IF NOT EXISTS pending_approval (
    user_id INTEGER PRIMARY KEY,
    invite_link TEXT NOT NULL
)
''')
conn.commit()

# Funzione per ottenere tutte le richieste in sospeso dal database
def get_pending_approval():
    cursor.execute('SELECT user_id, invite_link FROM pending_approval')
    return cursor.fetchall()

# Funzione per aggiungere una richiesta in sospeso al database
def add_pending_approval(user_id, invite_link):
    cursor.execute('INSERT INTO pending_approval (user_id, invite_link) VALUES (?, ?)', (user_id, invite_link))
    conn.commit()

# Funzione per rimuovere una richiesta approvata o rifiutata dal database
def remove_pending_approval(user_id):
    cursor.execute('DELETE FROM pending_approval WHERE user_id = ?', (user_id,))
    conn.commit()

# Funzione per verificare se un utente ha già ricevuto il link
def has_received_link(user_id):
    cursor.execute('SELECT user_id FROM pending_approval WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

# Funzione per gestire il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    user_id = user.id if user and user.id else None
    username = user.username if user and user.username else "Sconosciuto"
    
    if not user_id:
        await update.message.reply_text("Errore: ID utente non trovato.")
        return

    if has_received_link(user_id):
        await update.message.reply_text("Hai già ricevuto il link per unirti al canale.")
        return

    try:
        chat_invite_link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
        )
        add_pending_approval(user_id, chat_invite_link.invite_link)
        await update.message.reply_text(
            f"Sei stato aggiunto alla lista di Executed Ban, un amministratore approverà/rifiuterà la tua richiesta."
        )
        admin_ids = ["7839114402", "7768881599"]
        for admin_id in admin_ids:
            await context.bot.send_message(
                admin_id,
                f"Nuova richiesta di accesso al canale da @{username} (ID: {user_id}). Approva o rifiuta questa richiesta."
            )
    except Exception as e:
        await update.message.reply_text(f"Si è verificato un errore durante la creazione del link. Errore: {e}")
        logger.error(f"Errore durante la creazione del link di invito: {e}")

# Funzione per approvare un utente
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("Usa /approve <user_id> per approvare un utente.")
        return

    try:
        user_id = int(context.args[0])
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if not result:
            await update.message.reply_text("Questo utente non è in lista di attesa.")
            return

        chat_invite_link = result[0]
        await context.bot.send_message(
            user_id,
            f"Un amministratore ha approvato la tua richiesta per unirti al canale, Ecco il link per entrare {chat_invite_link}"
        )
        await update.message.reply_text(f"Utente {user_id} approvato e link inviato.")
        remove_pending_approval(user_id)
    except ValueError:
        await update.message.reply_text("ID utente non valido. Assicurati di inserire un numero valido.")

# Funzione per rifiutare un utente
async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("Usa /deny <user_id> <motivo> per rifiutare un utente.")
        return

    try:
        user_id = int(context.args[0])
        motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Nessun motivo"
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if not result:
            await update.message.reply_text("Questo utente non è in lista di attesa.")
            return

        await context.bot.send_message(
            user_id,
            f"Un amministratore ha rifiutato la tua richiesta per unirti al canale. Motivo: {motivo}"
        )
        await update.message.reply_text(f"Utente {user_id} rifiutato. Motivo: {motivo}")
        remove_pending_approval(user_id)
    except ValueError:
        await update.message.reply_text("ID utente non valido. Assicurati di inserire un numero valido.")

# Funzione per approvare tutte le richieste
async def approve_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    requests = get_pending_approval()
    if not requests:
        await update.message.reply_text("Non ci sono richieste in sospeso.")
        return

    for user_id, invite_link in requests:
        try:
            await context.bot.send_message(
                user_id,
                f"Un amministratore ha accettato la richiesta per unirti al canale, ecco il link per unirti {invite_link}"
            )
            await update.message.reply_text(f"Utente {user_id} approvato e link inviato.")
            remove_pending_approval(user_id)
        except Exception as e:
            logger.error(f"Errore nell'inviare il link a {user_id}: {e}")

# Stati della conversazione per /ban
TAG, MEMBERS = range(2)

# Funzione per iniziare il comando /ban
async def ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Inserisci il tag:")
    return TAG

# Funzione per gestire il tag inserito
async def ban_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tag = update.message.text.strip()
    context.user_data['tag'] = tag
    await update.message.reply_text("Inserisci i membri del canale (o scrivi 'salta' per ignorare):")
    return MEMBERS

# Funzione per gestire i membri inseriti
async def ban_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    members = update.message.text.strip()
    if members.lower() != "salta":
        context.user_data['members'] = members
    else:
        context.user_data['members'] = None

    tag = context.user_data.get('tag')
    members = context.user_data.get('members')
    message = (
        f"[😵] New Executed\n\n"
        f"[🎖️] Link : {tag}\n\n"
        f"[🦸🏻‍♂️] By : ✧ ₑₓₑcᵤₜₑd Bₐₙ ✧\n\n"
    )
    if members:
        message += f"[👥] Members: {members}\n\n"
    message += f"[📎] @executedban"

    try:
        await context.bot.send_message(CHANNEL_ID, message)
        await context.bot.send_message(GROUP_ID, message)
        await update.message.reply_text("Messaggio inviato con successo!")
    except Exception as e:
        await update.message.reply_text(f"Errore durante l'invio del messaggio: {e}")
        logger.error(f"Errore durante l'invio del messaggio: {e}")

    return ConversationHandler.END

# Funzione per annullare la conversazione
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operazione annullata.")
    return ConversationHandler.END

# Configurazione del bot
app = ApplicationBuilder().token(bot_token).build()

# Configura la conversazione per il comando /ban
ban_handler = ConversationHandler(
    entry_points=[CommandHandler("ban", ban_start)],
    states={
        TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, ban_tag)],
        MEMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ban_members)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# Aggiungi i gestori
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("deny", deny))
app.add_handler(CommandHandler("approveall", approve_all))
app.add_handler(ban_handler)

# Avvia il bot
if __name__ == "__main__":
    print("Bot in esecuzione...")
    app.run_polling()
