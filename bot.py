import os
from telegram.ext import ApplicationBuilder

bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("Il token non è stato trovato. Controlla le variabili d'ambiente.")

app = ApplicationBuilder().token(bot_token).build()
