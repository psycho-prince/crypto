import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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

# Enhanced HTML template with game-like UI
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto King</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background: linear-gradient(135deg, #1e3c72, #2a5298); color: white; }
        .container { margin-top: 20px; }
        .coin { font-size: 100px; cursor: pointer; transition: transform 0.2s; }
        .coin:hover { transform: scale(1.1); }
        .stats { margin: 10px; font-size: 22px; background: rgba(0, 0, 0, 0.5); padding: 10px; border-radius: 10px; }
        .message { color: #ffd700; font-size: 20px; }
        .energy-bar { width: 200px; height: 20px; background: #ccc; border-radius: 10px; margin: 10px auto; }
        .energy-fill { height: 100%; background: #00ff00; border-radius: 10px; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }
        .pulse { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ lang == 'ml' and 'ക്രിപ്റ്റോ രാജാവ്' or 'Crypto King' }}</h1>
        <div class="stats">👑 Level: {{ level }} | 💰 Coins: {{ "%.4f"|format(coins) }} </div>
        <div class="energy-bar"><div class="energy-fill" style="width: {{ energy }}%;"></div></div>
        <div class="stats">⚡ Energy: {{ energy }}/100</div>
        <div class="coin pulse" onclick="mine()">💰</div>
        <div id="message" class="message"></div>
    </div>
    <script>
        function mine() {
            fetch('/mine?user_id={{ user_id }}', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('message').innerText = data.message;
                    if (data.success) {
                        setTimeout(() => location.reload(), 500);  // Refresh after animation
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
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, "Player"))
        conn.commit()
        level, coins, energy, lang = 1, 0, 100, "en"
    else:
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
        message = "⚡ Energy Low! Wait or Boost!" if lang == "en" else "⚡ എനർജി കുറവാണ്! കാത്തിരിക്കുക അല്ലെങ്കിൽ ബൂസ്റ്റ് ചെയ്യുക!"
        return {"success": False, "message": message}
    coins_earned = random.uniform(0.002, 0.008)  # Slightly higher reward
    c.execute("UPDATE users SET coins = coins + ?, energy = energy - 10 WHERE user_id = ?", (coins_earned, user_id))
    conn.commit()
    message = f"🔨 +{coins_earned:.4f} Coins!" if lang == "en" else f"🔨 +{coins_earned:.4f} കോയിനുകൾ!"
    logger.info(f"User {user_id} mined {coins_earned} coins via web")
    return {"success": True, "message": message}

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Player"
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    lang = c.fetchone()[0]
    keyboard = [
        [InlineKeyboardButton("🎮 Mine Crypto", web_app=WebAppInfo(url=f"https://telebot-miner.psychoprince.repl.co?user_id={user_id}"))],
        [InlineKeyboardButton("🏆 Top Players", callback_data="top"), InlineKeyboardButton("⚡ Boost", callback_data="boost")],
        [InlineKeyboardButton("🌐 Lang: EN/ML", callback_data="lang")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = "👑 Welcome to Crypto King! Tap to mine FREE crypto!" if lang == "en" else "👑 ക്രിപ്റ്റോ രാജാവിലേക്ക് സ്വാഗതം! ഫ്രീ ക്രിപ്റ്റോ മൈൻ ചെയ്യൂ!"
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    logger.info(f"User {user_id} started the bot")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    lang = c.fetchone()[0] if c.fetchone() else "en"

    if query.data == "top":
        c.execute("SELECT username, coins FROM users ORDER BY coins DESC LIMIT 5")
        top_players = c.fetchall()
        top_text = "🏆 Top Miners\n" if lang == "en" else "🏆 മികച്ച മൈനർമാർ\n"
        for i, (username, coins) in enumerate(top_players, 1):
            top_text += f"{i}. @{username} - {coins:.4f} Coins\n"
        await query.edit_message_text(top_text)

    elif query.data == "boost":
        await query.edit_message_text("⚡ Boost coming soon! Invite friends to get more energy!" if lang == "en" else "⚡ ബൂസ്റ്റ് ഉടൻ വരുന്നു! കൂടുതൽ എനർജിക്കായി സുഹൃത്തുക്കളെ ക്ഷണിക്കുക!")

    elif query.data == "lang":
        c.execute("UPDATE users SET lang = ? WHERE user_id = ?", ("ml" if lang == "en" else "en", user_id))
        conn.commit()
        new_lang = "ml" if lang == "en" else "en"
        keyboard = [
            [InlineKeyboardButton("🎮 Mine Crypto", web_app=WebAppInfo(url=f"https://replit.com/@princephilip514/crypto?user_id={user_id}"))],
            [InlineKeyboardButton("🏆 Top Players", callback_data="top"), InlineKeyboardButton("⚡ Boost", callback_data="boost")],
            [InlineKeyboardButton("🌐 Lang: EN/ML", callback_data="lang")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Language switched!" if new_lang == "en" else "ഭാഷ മാറ്റി!", reply_markup=reply_markup)
    logger.info(f"User {user_id} pressed {query.data}")

# Main function
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set!")
        raise ValueError("Set TELEGRAM_TOKEN in .env or Replit Secrets")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Starting bot polling...")

    # Start Flask and keep-alive in threads
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True).start()

    # Background energy refill
    def refill_energy():
        while True:
            c.execute("UPDATE users SET energy = LEAST(energy + 10, 100) WHERE energy < 100")
            conn.commit()
            time.sleep(600)  # Refill 10 energy every 10 mins
    threading.Thread(target=refill_energy, daemon=True).start()

    application.run_polling()

if __name__ == "__main__":
    main()