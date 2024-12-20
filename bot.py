import os
import sqlite3
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
    raise ValueError("\ud83d\udea8 Il token non \u00e8 stato trovato. Controlla le variabili d'ambiente.")

# ID del canale (deve essere numerico, incluso il prefisso negativo)
CHANNEL_ID = -1002297768070  # Cambia con l'ID del tuo canale

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

# Funzione per verificare se un utente ha gi\u00e0 ricevuto il link
def has_received_link(user_id):
    cursor.execute('SELECT user_id FROM pending_approval WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

# Funzione per gestire il comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    user_id = user.id if user and user.id else None  # Controlla che user_id non sia None
    username = user.username if user and user.username else "Sconosciuto"

    if not user_id:
        await update.message.reply_text("\u274c Errore: ID utente non trovato.")
        return

    # Controlla se ci sono parametri passati con /start
    args = context.args
    if args and args[0] == "canale":
        await update.message.reply_text("BELLA BRO")
        return

    if has_received_link(user_id):  # Controlla se l'utente ha gi\u00e0 ricevuto il link
        await update.message.reply_text("\u26a0\ufe0f Hai gi\u00e0 ricevuto il link per unirti al canale.")
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
            f" Sei stato aggiunto alla lista di attesa. Un amministratore approver\u00e0 o rifiuter\u00e0 la tua richiesta. \ud83d\udd52"
        )

        # Notifica gli amministratori
        admin_ids = ["7839114402", "7768881599"]  # Aggiungi gli ID degli amministratori
        for admin_id in admin_ids:
            await context.bot.send_message(
                admin_id,
                f"\ud83d\udd14 Nuova richiesta di accesso al canale da @{username} (ID: {user_id}).\n"
                "Approva o rifiuta questa richiesta."
            )

    except Exception as e:
        # Gestisce eventuali errori
        await update.message.reply_text(f"\u274c Si \u00e8 verificato un errore durante la creazione del link. Errore: {e}")
        logger.error(f"Errore durante la creazione del link di invito: {e}")

# Funzione per approvare un utente
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("\u2753 Usa /approve <user_id> per approvare un utente.")
        return

    try:
        user_id = int(context.args[0])  # ID dell'utente da approvare

        # Recupera la richiesta dal database
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await update.message.reply_text("\u26a0\ufe0f Questo utente non \u00e8 in lista di attesa.")
            return

        chat_invite_link = result[0]

        # Invia il link di invito all'utente
        await context.bot.send_message(
            user_id,
            f"\u2705 Un amministratore ha approvato la tua richiesta! \nEcco il link per unirti al canale: {chat_invite_link}"
        )
        await update.message.reply_text(f"\ud83c\udf89 Utente {user_id} approvato e link inviato! \ud83d\udce8")

        # Rimuovi l'utente dal database
        remove_pending_approval(user_id)

    except ValueError:
        await update.message.reply_text("\u274c ID utente non valido. Assicurati di inserire un numero valido.")

# Funzione per rifiutare un utente
async def deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("\u2753 Usa /deny <user_id> <motivo> per rifiutare un utente.")
        return

    try:
        user_id = int(context.args[0])  # ID dell'utente da rifiutare
        motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Nessun motivo"

        # Recupera la richiesta dal database
        cursor.execute('SELECT invite_link FROM pending_approval WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if not result:
            await update.message.reply_text("\u26a0\ufe0f Questo utente non \u00e8 in lista di attesa.")
            return

        # Invia il messaggio di rifiuto all'utente
        await context.bot.send_message(
            user_id,
            f"\u274c La tua richiesta per unirti al canale \u00e8 stata rifiutata. \ud83d\ude14\nMotivo: {motivo}"
        )
        await update.message.reply_text(f"\u274c Utente {user_id} rifiutato. Motivo: {motivo}")

        # Rimuovi l'utente dal database
        remove_pending_approval(user_id)

    except ValueError:
        await update.message.reply_text("\u274c ID utente non valido. Assicurati di inserire un numero valido.")

# Funzione per approvare tutte le richieste
async def approve_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Ottieni tutte le richieste pendenti
    requests = get_pending_approval()
    if not requests:
        await update.message.reply_text("\ud83d\udce5 Non ci sono richieste in sospeso.")
        return

    for user_id, invite_link in requests:
        try:
            # Invia il link di invito a ciascun utente in attesa
            await context.bot.send_message(
                user_id,
                f"\u2705 Un amministratore ha accettato la tua richiesta! \ud83c\udf89\nEcco il link per unirti al canale: {invite_link}"
            )
            await update.message.reply_text(f"\ud83c\udf89 Utente {user_id} approvato e link inviato! \ud83d\udce8")

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
    print("\ud83e\udd16 Bot in esecuzione...")
    app.run_polling()
