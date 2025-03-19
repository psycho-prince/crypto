import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, coins REAL DEFAULT 0, energy INTEGER DEFAULT 100, level INTEGER DEFAULT 1, lang TEXT DEFAULT 'en')")
conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Player"
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    repl_domain = "https://crypto-king.onrender.com"  # Replace with your actual Repl URL
    web_app_url = f"{repl_domain}?user_id={user_id}"
    keyboard = [[InlineKeyboardButton("🎮 Start Mining", web_app=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👑 Crypto King: Solve Puzzles, Mine Coins!", reply_markup=reply_markup)
    logger.info(f"User {user_id} started bot, Web App URL: {web_app_url}")

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set!")
        raise ValueError("Set TELEGRAM_TOKEN in .env or Replit Secrets")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
