import os
import mysql.connector
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
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

# Connessione al database MySQL
db_host = os.getenv("MYSQLHOST")
db_port = os.getenv("MYSQLPORT")
db_user = os.getenv("MYSQLUSER")
db_password = os.getenv("MYSQLPASSWORD")
db_name = os.getenv("MYSQLDATABASE")

# Crea una connessione MySQL
def get_db_connection():
    return mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name
    )

# Funzione per ottenere tutte le richieste in sospeso dal database
def get_pending_approval():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, invite_link FROM pending_approval')
    result = cursor.fetchall()
    conn.close()
    return result

# Funzione per aggiungere una richiesta in sospeso al database
def add_pending_approval(user_id, invite_link):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pending_approval (user_id, invite_link) VALUES (%s, %s)', (user_id, invite_link))
    conn.commit()
    conn.close()

# Funzione per rimuovere una richiesta approvata o rifiutata dal database
def remove_pending_approval(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM pending_approval WHERE user_id = %s', (user_id,))
    conn.commit()
    conn.close()

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
        
        # Aggiungi l'utente al database
        add_pending_approval(user_id, chat_invite_link.invite_link)
        
        # Invia il messaggio di attesa
        await update.message.reply_text(
            f"Sei stato aggiunto alla lista di attesa per entrare nel canale 'Executed Ban'. "
            "Un amministratore dovrà approvarti. Ti invierò il link appena approvato."
        )
        
        # Notifica l'amministratore (puoi sostituire con il tuo ID Telegram)
        admin_id =  ["7839114402", "7768881599"]  # Sostituisci con l'ID dell'amministratore
        await context.bot.send_message(
            admin_id,
            f"Nuova richiesta di accesso al canale da {username} (ID: {user_id})."
            " Approva o rifiuta questa richiesta."
        )
    
    except Exception as e:
        # Gestisce eventuali errori
        await update.message.reply_text("Si è verificato un errore durante la creazione del link.")
        logger.error(f"Errore: {e}")

# Funzione per approvare un utente
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Verifica che ci sia un ID utente
    if len(context.args) != 1:
        await update.message.reply_text("Sintassi errata! Usa /approve <user_id> per approvare un utente.")
        return

    try:
        user_id = int(context.args[0])  # ID dell'utente da approvare

        # Recupera la richiesta dal database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text("Questo utente non è in lista di attesa.")
            return

        chat_invite_link = result[0]

        # Invia il link di invito all'utente
        await context.bot.send_message(
            user_id,
            f"Il tuo accesso al canale 'Executed Ban' è stato approvato. Ecco il link per entrare: {chat_invite_link}"
        )
        await update.message.reply_text(f"Utente {user_id} approvato e link inviato.")

        # Rimuovi l'utente dal database
        remove_pending_approval(user_id)

    except ValueError:
        await update.message.reply_text("ID utente non valido. Assicurati di inserire un numero valido.")

# Funzione per rifiutare un utente
async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Verifica che ci siano due argomenti: user_id e motivo
    if len(context.args) < 1:
        await update.message.reply_text("Sintassi errata! Usa /deny <user_id> <motivo> per rifiutare un utente.")
        return

    try:
        user_id = int(context.args[0])  # ID dell'utente da rifiutare
        motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Nessun motivo fornito."

        # Recupera la richiesta dal database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text("Questo utente non è in lista di attesa.")
            return

        # Invia il messaggio di rifiuto all'utente
        await context.bot.send_message(
            user_id,
            f"Mi dispiace, la tua richiesta di accesso al canale 'Executed Ban' è stata rifiutata. "
            f"Motivo: {motivo}"
        )
        await update.message.reply_text(f"Utente {user_id} rifiutato. Motivo: {motivo}")

        # Rimuovi l'utente dal database
        remove_pending_approval(user_id)

    except ValueError:
        await update.message.reply_text("ID utente non valido. Assicurati di inserire un numero valido.")

# Funzione per approvare tutte le richieste
async def approve_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Ottieni tutte le richieste pendenti
    requests = get_pending_approval()
    if not requests:
        await update.message.reply_text("Non ci sono richieste in sospeso.")
        return

    for user_id, invite_link in requests:
        try:
            # Invia il link di invito a ciascun utente in attesa
            await context.bot.send_message(
                user_id,
                f"Il tuo accesso al canale 'Executed Ban' è stato approvato. Ecco il link per entrare: {invite_link}"
            )
            await update.message.reply_text(f"Utente {user_id} approvato e link inviato.")

            # Rimuovi l'utente dal database
            remove_pending_approval(user_id)
        except Exception as e:
            logger.error(f"Errore nell'inviare il link a {user_id}: {e}")

# Configurazione del bot
app = ApplicationBuilder().token(bot_token).build()

# Aggiungi il gestore per il comando /start
app.add_handler(CommandHandler("start", start))

# Aggiungi il gestore per l'approvazione
app.add_handler(CommandHandler("approve", approve))

# Aggiungi il gestore per il rifiuto
app.add_handler(CommandHandler("deny", deny))

# Aggiungi il gestore per l'approvazione di tutti gli utenti
app.add_handler(CommandHandler("approveall", approve_all))

# Avvia il bot
if __name__ == "__main__":
    print("Bot in esecuzione...")
    app.run_polling()
