import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask, request, render_template_string, jsonify
import threading
import time
from dotenv import load_dotenv
import random

# Load .env file (local use; Replit uses Secrets)
load_dotenv()

# Logging setup with more detail
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, coins REAL DEFAULT 0, energy INTEGER DEFAULT 100, level INTEGER DEFAULT 1, lang TEXT DEFAULT 'en')")
conn.commit()

# Flask app for HTML UI
app = Flask(__name__)

# Simplified HTML template for debugging
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto King</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background: #1e3c72; color: white; }
        .container { margin-top: 20px; }
        h1 { font-size: 32px; }
        .stats { font-size: 18px; }
        button { padding: 10px 20px; font-size: 16px; background: #ffd700; color: #000; border: none; border-radius: 8px; cursor: pointer; margin: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Crypto King</h1>
        <div class="stats">User ID: {{ user_id }} | Coins: {{ "%.4f"|format(coins) }} | Energy: {{ energy }}</div>
        <button onclick="alert('Test Button Works!')">Test Button</button>
        <button onclick="window.Telegram.WebApp.close()">Exit</button>
    </div>
</body>
</html>
"""

# Flask routes
@app.route('/')
def home():
    user_id = request.args.get('user_id')
    logger.info(f"Received request for user_id: {user_id}")
    if not user_id:
        logger.error("No user_id provided")
        return "User ID required", 400
    c.execute("SELECT coins, energy FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, "Player"))
        conn.commit()
        coins, energy = 0, 100
    else:
        coins, energy = user_data
    logger.info(f"Serving UI for user_id: {user_id}")
    return render_template_string(html_template, user_id=user_id, coins=coins, energy=energy)

# Bot command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Player"
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    # Update this URL to your actual Repl domain
    repl_domain = "https://replit.com/@princephilip514"  # Replace with your Repl URL
    web_app_url = f"{repl_domain}?user_id={user_id}"
    keyboard = [[InlineKeyboardButton("🎮 Start Mining", web_app=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👑 Crypto King: Solve Puzzles, Mine Coins!", reply_markup=reply_markup)
    logger.info(f"User {user_id} started bot, Web App URL: {web_app_url}")

# Main function
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set!")
        raise ValueError("Set TELEGRAM_TOKEN in .env or Replit Secrets")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    logger.info("Starting bot polling...")

    # Start Flask in a thread
    def run_flask():
        logger.info("Starting Flask on 0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    threading.Thread(target=run_flask, daemon=True).start()

    # Background energy refill
    def refill_energy():
        while True:
            thread_conn = sqlite3.connect("users.db", check_same_thread=False)
            thread_c = thread_conn.cursor()
            try:
                thread_c.execute("UPDATE users SET energy = LEAST(energy + 10, 100) WHERE energy < 100")
                thread_conn.commit()
                logger.info("Energy refilled for users")
            except Exception as e:
                logger.error(f"Error in refill_energy: {e}")
            finally:
                thread_conn.close()
            time.sleep(600)  # Refill 10 energy every 10 mins
    threading.Thread(target=refill_energy, daemon=True).start()

    application.run_polling()

if __name__ == "__main__":
    main()