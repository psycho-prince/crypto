import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User{user_id}"
    repl_domain = "https://crypto-king.onrender.com"  # Updated to Render URL
    web_app_url = f"{repl_domain}/?user_id={user_id}"
    keyboard = [[InlineKeyboardButton("🎮 Play Crypto King", web_app=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👑 Welcome to Crypto King!\nTap below to start mining coins!",
        reply_markup=reply_markup
    )
    logger.info(f"User {user_id} ({username}) started bot, Web App URL: {web_app_url}")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set!")
        raise ValueError("Set TELEGRAM_TOKEN in environment variables")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
