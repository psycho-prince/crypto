import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or "Unknown"
    
    keyboard = [[InlineKeyboardButton("Play Crypto King", url=f"https://crypto-king.onrender.com/?user_id={user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Welcome, {username}! 👑\nTap below to start mining in Crypto King!",
        reply_markup=reply_markup
    )
    logger.info(f"User {user_id} ({username}) started bot, Web App URL: https://crypto-king.onrender.com/?user_id={user_id}")

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    logger.info("Starting bot polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
