import os
import mysql.connector
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging
from datetime import datetime, timedelta

# Configura il logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Ottieni il token dalla variabile d'ambiente
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("🚨 Token mancante. Controlla le variabili d'ambiente.")

# ID del canale (deve essere numerico, incluso il prefisso negativo)
CHANNEL_ID = -1002297768070  # Cambia con l'ID del tuo canale

# Configurazione della connessione al database MySQL
db_connection = mysql.connector.connect(
    host="mysql.railway.internal",  # Host del database MySQL
    user="root",  # Nome utente del database MySQL
    password="SkLZXExebspawlyFsxoahOZCFWUTcPvM",  # Password del database MySQL
    database="railway",  # Nome del database
    port=3306  # Porta del database
)
cursor = db_connection.cursor()

# Crea la tabella per le richieste in sospeso se non esiste
cursor.execute('''
CREATE TABLE IF NOT EXISTS pending_approval (
    user_id BIGINT PRIMARY KEY,
    invite_link TEXT NOT NULL
)
''')
db_connection.commit()

# Funzione per ottenere tutte le richieste in sospeso dal database
def get_pending_approval():
    cursor.execute('SELECT user_id, invite_link FROM pending_approval')
    return cursor.fetchall()

# Funzione per aggiungere una richiesta in sospeso al database
def add_pending_approval(user_id, invite_link):
    cursor.execute('INSERT INTO pending_approval (user_id, invite_link) VALUES (%s, %s)', (user_id, invite_link))
    db_connection.commit()

# Funzione per rimuovere una richiesta approvata o rifiutata dal database
def remove_pending_approval(user_id):
    cursor.execute('DELETE FROM pending_approval WHERE user_id = %s', (user_id,))
    db_connection.commit()

# Funzione per verificare se un utente ha già ricevuto il link
def has_received_link(user_id):
    cursor.execute('SELECT user_id FROM pending_approval WHERE user_id = %s', (user_id,))
    return cursor.fetchone() is not None

# Funzione per gestire il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    user_id = user.id if user and user.id else None  # Controlla che user_id non sia None
    username = user.username if user and user.username else "Sconosciuto"
    
    if not user_id:
        await update.message.reply_text("❌ Non riesco a trovare il tuo ID, sembra che ci sia un errore.")
        return

    if has_received_link(user_id):  # Controlla se l'utente ha già ricevuto il link
        await update.message.reply_text("⚠️ Hai già ricevuto il link per il canale!")
        return

    try:
        # Crea un nuovo link di invito valido per una sola persona e che scade dopo 10 minuti
        expire_time = datetime.now() + timedelta(minutes=1)
        chat_invite_link: ChatInviteLink = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,  # Limita il link a un solo utilizzo
            expire_date=expire_time.timestamp()  # Scade dopo 10 minuti
        )
        
        # Aggiungi l'utente al database
        add_pending_approval(user_id, chat_invite_link.invite_link)
        
        # Invia il messaggio di attesa
        await update.message.reply_text(
            f"Ti ho aggiunto alla lista d'attesa! Un admin ti farà sapere se puoi entrare. ⏳"
        )
        
        # Notifica gli amministratori
        admin_ids = ["7839114402", "7768881599"]  # Aggiungi gli ID degli amministratori
        for admin_id in admin_ids:
            await context.bot.send_message(
                admin_id,
                f"🔔 Nuova richiesta di accesso da @{username} (ID: {user_id}). Decidi se approvarla."
            )
    
    except Exception as e:
        # Gestisce eventuali errori
        await update.message.reply_text(f"❌ Si è verificato un errore. Errore: {e}")
        logger.error(f"Errore durante la creazione del link di invito: {e}")

# Funzione per approvare un utente
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("❓ Usa /approve <user_id> per approvare un utente.")
        return

    try:
        user_id = int(context.args[0])  # ID dell'utente da approvare

        # Recupera la richiesta dal database
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()

        if not result:
            await update.message.reply_text("⚠️ Questo utente non è in lista di attesa.")
            return

        chat_invite_link = result[0]

        # Invia il link di invito all'utente
        await context.bot.send_message(
            user_id,
            f"✅ La tua richiesta è stata approvata! Ecco il link per entrare nel canale: {chat_invite_link}"
        )

        # Notifica tutti gli amministratori
        admin_ids = ["7839114402", "7768881599"]
        for admin_id in admin_ids:
            await context.bot.send_message(
                admin_id,
                f"🎉 La richiesta dell'utente {user_id} è stata approvata, il link è stato inviato!"
            )

        # Rimuovi l'utente dal database
        remove_pending_approval(user_id)

    except ValueError:
        await update.message.reply_text("❌ L'ID che hai inserito non è valido. Prova con un numero giusto.")
    except Exception as e:
        logger.error(f"Errore nell'approvazione dell'utente: {e}")
        await update.message.reply_text("❌ Si è verificato un errore.")

# Funzione per approvare tutti gli utenti
async def approve_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending_requests = get_pending_approval()
    for user_id, invite_link in pending_requests:
        try:
            await context.bot.send_message(
                user_id,
                f"✅ La tua richiesta è stata approvata! Ecco il link per entrare nel canale: {invite_link}"
            )
        except Exception as e:
            logger.error(f"Errore nell'invio del link all'utente {user_id}: {e}")
        finally:
            remove_pending_approval(user_id)

    await update.message.reply_text("🎉 Tutte le richieste sono state approvate!")

# Funzione per rifiutare una richiesta
async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("❓ Usa /deny <user_id> per rifiutare una richiesta.")
        return

    try:
        user_id = int(context.args[0])
        remove_pending_approval(user_id)
        await update.message.reply_text(f"❌ La richiesta dell'utente {user_id} è stata rifiutata.")
    except ValueError:
        await update.message.reply_text("❌ L'ID che hai inserito non è valido.")
    except Exception as e:
        logger.error(f"Errore durante il rifiuto dell'utente {user_id}: {e}")
        await update.message.reply_text("❌ Si è verificato un errore.")

# Configura l'applicazione Telegram
application = ApplicationBuilder().token(bot_token).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("approve", approve))
application.add_handler(CommandHandler("approveall", approve_all))
application.add_handler(CommandHandler("deny", deny))

if __name__ == "__main__":
    logger.info("Bot in esecuzione...")
    application.run_polling()
