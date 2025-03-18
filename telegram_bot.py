import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, request, render_template_string
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

# Flask app for HTML UI
app = Flask(__name__)

# HTML template for Web App (simple tap-to-mine UI)
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto King</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background: #f0f0f0; }
        .container { margin-top: 50px; }
        .coin { font-size: 48px; cursor: pointer; }
        .stats { margin: 20px; font-size: 24px; }
        button { padding: 10px 20px; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ lang == 'ml' and 'ക്രിപ്റ്റോ കിംഗ്' or 'Crypto King' }}</h1>
        <div class="stats">Level: {{ level }} | Coins: {{ "%.4f"|format(coins) }} | Energy: {{ energy }}</div>
        <div class="coin" onclick="mine()">💰</div>
        <p>{{ lang == 'ml' and 'കോയിനുകൾ നേടാൻ ടാപ്പ് ചെയ്യൂ!' or 'Tap to Earn Coins!' }}</p>
        <div id="message"></div>
    </div>
    <script>
        function mine() {
            fetch('/mine?user_id={{ user_id }}', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('message').innerText = data.message;
                    if (data.success) {
                        location.reload();  // Refresh stats
                    }
                });
        }
    </script>
</body>
</html>
"""

# Flask routes
@app.route('/')
def home():
    user_id = request.args.get('user_id')
    if not user_id:
        return "User ID required", 400
    c.execute("SELECT level, coins, energy, lang FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        return "User not found", 404
    level, coins, energy, lang = user_data
    return render_template_string(html_template, user_id=user_id, level=level, coins=coins, energy=energy, lang=lang)

@app.route('/mine', methods=['POST'])
def mine_web():
    user_id = request.args.get('user_id')
    c.execute("SELECT energy, coins, lang FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        return {"success": False, "message": "User not found"}, 404
    energy, coins, lang = user_data
    if energy < 10:
        message = "⚡ No energy left! Wait or invite friends!" if lang == "en" else "⚡ എനർജി തീർന്നു! കാത്തിരിക്കുക അല്ലെങ്കിൽ സുഹൃത്തുക്കളെ ക്ഷണിക്കുക!"
        return {"success": False, "message": message}
    coins_earned = random.uniform(0.001, 0.005)
    c.execute("UPDATE users SET coins = coins + ?, energy = energy - 10 WHERE user_id = ?", (coins_earned, user_id))
    conn.commit()
    message = f"🔨 Mined {coins_earned:.4f} coins! Tap again!" if lang == "en" else f"🔨 {coins_earned:.4f} കോയിനുകൾ മൈൻ ചെയ്തു! വീണ്ടും ടാപ്പ് ചെയ്യൂ!"
    logger.info(f"User {user_id} mined {coins_earned} coins via web")
    return {"success": True, "message": message}

# Keep-alive server for Replit
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_server():
    server = HTTPServer(("", 8080), KeepAlive)
    server.serve_forever()

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Player"
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    keyboard = [[InlineKeyboardButton("🎮 Play Now", web_app=WebAppInfo(url=f"https://telebot-miner.psychoprince.repl.co?user_id={user_id}"))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to Crypto King! Tap to mine FREE crypto!", reply_markup=reply_markup)
    logger.info(f"User {user_id} started the bot")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    lang = c.fetchone()[0] if c.fetchone() else "en"
    help_text = (
        "en" if lang == "en" else "ml",
        "🎮 **How to Play Crypto King** 🎮\n"
        "1. Search '@YourBotName' in Telegram.\n"
        "2. Type /start and tap 'Play Now'.\n"
        "3. Tap the coin to earn FREE crypto!\n"
        "4. Energy refills every 10 mins.\n"
        "5. Use /lang ml for Malayalam.\n"
        "💰 Tap more, win BIG like Hamster Kombat! 💰" if lang == "en" else
        "🎮 **ക്രിപ്റ്റോ കിംഗ് എങ്ങനെ കളിക്കാം** 🎮\n"
        "1. ടെലിഗ്രാമിൽ '@YourBotName' തിരയുക.\n"
        "2. /start ടൈപ്പ് ചെയ്ത് 'ഇപ്പോൾ കളിക്കുക' ടാപ്പ് ചെയ്യുക.\n"
        "3. കോയിനിൽ ടാപ്പ് ചെയ്ത് ഫ്രീ ക്രിപ്റ്റോ നേടുക!\n"
        "4. എനർജി ഓരോ 10 മിനിറ്റിലും നിറയും.\n"
        "5. /lang ml ഉപയോഗിച്ച് മലയാളം തിരഞ്ഞെടുക്കുക.\n"
        "💰 കൂടുതൽ ടാപ്പ്, ഹാംസ്റ്റർ കോമ്പാറ്റിനെപ്പോലെ വലിയ സമ്മാനങ്ങൾ! 💰"
    )[1]
    await update.message.reply_text(help_text)
    logger.info(f"User {user_id} requested help")

async def lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    lang = args[0] if args else "en"
    if lang not in ["en", "ml"]:
        await update.message.reply_text("Use /lang en or /lang ml")
        return
    c.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    await update.message.reply_text("Language set to English!" if lang == "en" else "ഭാഷ മലയാളമായി സജ്ജമാക്കി!")
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
    application.add_handler(CommandHandler("lang", lang))
    logger.info("Starting bot polling...")

    # Start Flask and keep-alive in threads
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True).start()

    # Background energy refill
    def refill_energy():
        while True:
            try:
                # Create a new connection for this thread
                thread_conn = sqlite3.connect("users.db")
                thread_c = thread_conn.cursor()
                # Use MIN instead of LEAST for SQLite compatibility
                thread_c.execute("UPDATE users SET energy = MIN(energy + 10, 100) WHERE energy < 100")
                thread_conn.commit()
                thread_conn.close()
            except Exception as e:
                logger.error(f"Error in refill_energy: {e}")
            time.sleep(600)  # Refill 10 energy every 10 mins
    threading.Thread(target=refill_energy, daemon=True).start()

    application.run_polling()

if __name__ == "__main__":
    main()