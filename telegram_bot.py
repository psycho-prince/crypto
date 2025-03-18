import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
from dotenv import load_dotenv
import random

# Load .env file (local use; Replit uses Secrets)
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect("users.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, coins REAL DEFAULT 0, energy INTEGER DEFAULT 100, level INTEGER DEFAULT 1, lang TEXT DEFAULT 'en')")
conn.commit()

# Keep-alive server for Replit
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_server():
    server = HTTPServer(("", 8080), KeepAlive)
    server.serve_forever()

# Game-like mining simulation
def simulate_mining(user_id):
    coins_earned = random.uniform(0.001, 0.005)  # Simulated "crypto" coins
    c.execute("UPDATE users SET coins = coins + ?, energy = energy - 10 WHERE user_id = ?", (coins_earned, user_id))
    conn.commit()
    return coins_earned

# Language translations
translations = {
    "en": {
        "welcome": "Welcome to Crypto King! Tap to mine FREE crypto! Use /help for guide.",
        "help": (
            "🎮 **How to Play Crypto King** 🎮\n"
            "1. Search '@YourBotName' in Telegram.\n"
            "2. Type /start to join the game.\n"
            "3. Tap 'Mine Now' to earn FREE crypto coins!\n"
            "4. Check /status for your coins & energy.\n"
            "5. Use /lang to switch to Malayalam.\n"
            "💰 More taps = More crypto! Top players win BIG! 💰"
        ),
        "status": "👑 Level: {}\n💰 Coins: {:.4f}\n⚡ Energy: {}\nTap 'Mine Now' to earn more!",
        "mine": "🔨 Mining... You earned {:.4f} coins! Tap again!",
        "no_energy": "⚡ No energy left! Wait 10 mins or invite friends to refill!",
        "lang_set": "Language set to English!",
    },
    "ml": {  # Malayalam
        "welcome": "ക്രിപ്റ്റോ കിംഗിലേക്ക് സ്വാഗതം! ഫ്രീ ക്രിപ്റ്റോ മൈൻ ചെയ്യാൻ ടാപ്പ് ചെയ്യൂ! /help ഉപയോഗിക്കുക.",
        "help": (
            "🎮 **ക്രിപ്റ്റോ കിംഗ് എങ്ങനെ കളിക്കാം** 🎮\n"
            "1. ടെലിഗ്രാമിൽ '@YourBotName' തിരയുക.\n"
            "2. /start ടൈപ്പ് ചെയ്ത് ഗെയിം തുടങ്ങുക.\n"
            "3. 'ഇപ്പോൾ മൈൻ ചെയ്യുക' ടാപ്പ് ചെയ്ത് ഫ്രീ ക്രിപ്റ്റോ നേടുക!\n"
            "4. /status ഉപയോഗിച്ച് നിന്റെ കോയിനുകളും എനർജിയും പരിശോധിക്കുക.\n"
            "5. /lang ഉപയോഗിച്ച് മലയാളത്തിലേക്ക് മാറുക.\n"
            "💰 കൂടുതൽ ടാപ്പ് = കൂടുതൽ ക്രിപ്റ്റോ! ടോപ്പ് പ്ലെയർമാർ വലിയ സമ്മാനങ്ങൾ നേടും! 💰"
        ),
        "status": "👑 ലെവൽ: {}\n💰 കോയിനുകൾ: {:.4f}\n⚡ എനർജി: {}\nകൂടുതൽ നേടാൻ 'ഇപ്പോൾ മൈൻ ചെയ്യുക' ടാപ്പ് ചെയ്യുക!",
        "mine": "🔨 മൈനിങ്... നിനക്ക് {:.4f} കോയിനുകൾ കിട്ടി! വീണ്ടും ടാപ്പ് ചെയ്യൂ!",
        "no_energy": "⚡ എനർജി തീർന്നു! 10 മിനിറ്റ് കാത്തിരിക്കുക അല്ലെങ്കിൽ സുഹൃത്തുക്കളെ ക്ഷണിക്കുക!",
        "lang_set": "ഭാഷ മലയാളമായി സജ്ജമാക്കി!",
    }
}

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Player"
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    lang = c.fetchone()[0]
    await update.message.reply_text(translations[lang]["welcome"])
    logger.info(f"User {user_id} started the bot")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    lang = c.fetchone()[0]
    await update.message.reply_text(translations[lang]["help"])
    logger.info(f"User {user_id} requested help")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT level, coins, energy, lang FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        await update.message.reply_text("Start with /start first!")
        return
    level, coins, energy, lang = user_data
    keyboard = [[InlineKeyboardButton("Mine Now", callback_data="mine")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(translations[lang]["status"].format(level, coins, energy), reply_markup=reply_markup)
    logger.info(f"User {user_id} checked status")

async def mine_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    c.execute("SELECT energy, coins, lang FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        await query.answer("Register first with /start!")
        return
    energy, coins, lang = user_data
    if energy < 10:
        await query.answer(translations[lang]["no_energy"])
        return
    coins_earned = simulate_mining(user_id)
    await query.edit_message_text(translations[lang]["mine"].format(coins_earned))
    logger.info(f"User {user_id} mined {coins_earned} coins")

async def lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    lang = args[0] if args else "en"
    if lang not in ["en", "ml"]:
        await update.message.reply_text("Use /lang en or /lang ml")
        return
    c.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    await update.message.reply_text(translations[lang]["lang_set"])
    logger.info(f"User {user_id} set language to {lang}")

# Main function
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set!")
        raise ValueError("Set TELEGRAM_TOKEN in .env or Replit Secrets")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("lang", lang))
    application.add_handler(CallbackQueryHandler(mine_callback, pattern="mine"))
    logger.info("Starting bot polling...")
    threading.Thread(target=run_server, daemon=True).start()
    # Background energy refill
    def refill_energy():
        while True:
            try:
                # Create a new connection for this thread
                thread_conn = sqlite3.connect("users.db")
                thread_c = thread_conn.cursor()
                thread_c.execute("UPDATE users SET energy = LEAST(energy + 10, 100) WHERE energy < 100")
                thread_conn.commit()
                thread_conn.close()
            except Exception as e:
                logger.error(f"Error in refill_energy: {e}")
            time.sleep(600)  # Refill 10 energy every 10 minutes
    threading.Thread(target=refill_energy, daemon=True).start()
    application.run_polling()

if __name__ == "__main__":
    main()