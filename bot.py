import os
import sqlite3
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging
import asyncio

# Configura il logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Ottieni il token dalla variabile d'ambiente
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("Il token non è stato trovato. Controlla le variabili d'ambiente.")

# ID del canale (deve essere numerico, incluso il prefisso negativo)
CHANNEL_ID = -1002297768070  # Cambia con l'ID del tuo canale
ADMIN_ID = 7839114402  # ID dell'amministratore da notificare

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

# Struttura dati per monitorare gli ID
monitored_ids = {}

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
    user_id = user.id if user and user.id else None  # Controlla che user_id non sia None
    username = user.username if user and user.username else "Sconosciuto"
    
    if not user_id:
        await update.message.reply_text("Errore: ID utente non trovato.")
        return

    if has_received_link(user_id):  # Controlla se l'utente ha già ricevuto il link
        await update.message.reply_text("Hai già ricevuto il link per unirti al canale.")
        return

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
            f"Sei stato aggiunto alla lista di Executed Ban, un amministratore approverà/rifiuterà la tua richiesta."
        )
        
        # Notifica gli amministratori
        admin_ids = ["7839114402", "7768881599"]  # Aggiungi gli ID degli amministratori
        for admin_id in admin_ids:
            await context.bot.send_message(
                admin_id,
                f"Nuova richiesta di accesso al canale da @{username} (ID: {user_id})."
                " Approva o rifiuta questa richiesta."
            )
    
    except Exception as e:
        # Gestisce eventuali errori
        await update.message.reply_text(f"Si è verificato un errore durante la creazione del link. Errore: {e}")
        logger.error(f"Errore durante la creazione del link di invito: {e}")

# Funzione per approvare un utente
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("Usa /approve <user_id> per approvare un utente.")
        return

    try:
        user_id = int(context.args[0])  # ID dell'utente da approvare

        # Recupera la richiesta dal database
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await update.message.reply_text("Questo utente non è in lista di attesa.")
            return

        chat_invite_link = result[0]

        # Invia il link di invito all'utente
        await context.bot.send_message(
            user_id,
            f"Un amministratore ha approvato la tua richiesta per unirti al canale, Ecco il link per entrare {chat_invite_link}"
        )
        await update.message.reply_text(f"Utente {user_id} approvato e link inviato.")

        # Rimuovi l'utente dal database
        remove_pending_approval(user_id)

    except ValueError:
        await update.message.reply_text("ID utente non valido. Assicurati di inserire un numero valido.")

# Funzione per rifiutare un utente
async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("Usa /deny <user_id> <motivo> per rifiutare un utente.")
        return

    try:
        user_id = int(context.args[0])  # ID dell'utente da rifiutare
        motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Nessun motivo"

        # Recupera la richiesta dal database
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await update.message.reply_text("Questo utente non è in lista di attesa.")
            return

        # Invia il messaggio di rifiuto all'utente
        await context.bot.send_message(
            user_id,
            f"Un amministratore ha rifiutato la tua richiesta per unirti al canale. "
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
                f"Un amministratore ha accettato la richiesta per unirti al canale, ecco il link per unirti {invite_link}"
            )
            await update.message.reply_text(f"Utente {user_id} approvato e link inviato.")

            # Rimuovi l'utente dal database
            remove_pending_approval(user_id)
        except Exception as e:
            logger.error(f"Errore nell'inviare il link a {user_id}: {e}")

# Funzione per verificare se un canale, gruppo o account esiste
async def check_entity_existence(context: ContextTypes.DEFAULT_TYPE, entity_id: str):
    try:
        await context.bot.get_chat(chat_id=entity_id)
        return True
    except Exception as e:
        return False

# Loop asincrono per monitorare gli ID
async def monitor_entities(context: ContextTypes.DEFAULT_TYPE):
    while True:
        for entity_id in list(monitored_ids.keys()):
            if not await check_entity_existence(context, entity_id):
                # Se l'entità non esiste più, invia una notifica all'amministratore
                await context.bot.send_message(
                    ADMIN_ID,
                    f"Il canale/gruppo/account con ID {entity_id} è stato eliminato."
                )
                del monitored_ids[entity_id]
        await asyncio.sleep(10)

# Funzione per gestire il comando /sniper
async def sniper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("Usa /sniper <canale/gruppo/account ID> per monitorare un'entità.")
        return

    entity_id = context.args[0]

    if entity_id in monitored_ids:
        await update.message.reply_text("Questo ID è già monitorato.")
        return

    # Aggiungi l'ID alla lista degli ID monitorati
    monitored_ids[entity_id] = True
    await update.message.reply_text(f"L'ID {entity_id} è ora monitorato.")

# Funzione per gestire il comando /stop_sniper
async def stop_sniper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("Usa /stop_sniper <canale/gruppo/account ID> per smettere di monitorare un'entità.")
        return

    entity_id = context.args[0]

    if entity_id not in monitored_ids:
        await update.message.reply_text("Questo ID non è monitorato.")
        return

    # Rimuovi l'ID dalla lista degli ID monitorati
    del monitored_ids[entity_id]
    await update.message.reply_text(f"L'ID {entity_id} non è più monitorato.")

# Configurazione del bot
app = ApplicationBuilder().token(bot_token).build()

# Aggiungi il gestore per il comando /start
app.add_handler(CommandHandler("start", start))

# Aggiungi il gestore per il comando /approve
app.add_handler(CommandHandler("approve", approve))

# Aggiungi il gestore per il comando /deny
app.add_handler(CommandHandler("deny", deny))

# Aggiungi il gestore per il comando /approveall
app.add_handler(CommandHandler("approveall", approve_all))

# Aggiungi il gestore per il comando /sniper
app.add_handler(CommandHandler("sniper", sniper))

# Aggiungi il gestore per il comando /stop_sniper
app.add_handler(CommandHandler("stop_sniper", stop_sniper))

# Avvia il loop di monitoraggio quando il bot inizia
app.job_queue.run_repeating(monitor_entities, interval=10, first=0)

# Avvia il bot
if __name__ == "__main__":
    print("Bot in esecuzione...")
    app.run_polling()
