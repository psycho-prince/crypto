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

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, coins REAL DEFAULT 0, energy INTEGER DEFAULT 100, level INTEGER DEFAULT 1, lang TEXT DEFAULT 'en')")
conn.commit()

# Flask app for HTML UI
app = Flask(__name__)

# Enhanced HTML template with puzzle-based mining UI
html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto King</title>
    <style>
        body { font-family: 'Arial', sans-serif; text-align: center; background: linear-gradient(135deg, #2a5298, #1e3c72); color: #fff; margin: 0; padding: 0; }
        .container { padding: 20px; max-width: 600px; margin: 0 auto; }
        h1 { font-size: 32px; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
        .stats { background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 10px; margin-bottom: 20px; font-size: 18px; }
        .energy-bar { width: 80%; height: 20px; background: #444; border-radius: 10px; margin: 10px auto; }
        .energy-fill { height: 100%; background: linear-gradient(to right, #00ff00, #00cc00); border-radius: 10px; }
        .puzzle { background: rgba(0, 0, 0, 0.3); padding: 20px; border-radius: 15px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 20px auto; width: 200px; }
        .tile { width: 60px; height: 60px; background: #ffd700; color: #000; font-size: 24px; display: flex; align-items: center; justify-content: center; border-radius: 8px; cursor: pointer; transition: transform 0.2s; }
        .tile:hover { transform: scale(1.05); }
        .tile.matched { background: #00ff00; }
        .message { color: #ffd700; font-size: 20px; margin-top: 20px; }
        .leaderboard { margin-top: 20px; font-size: 16px; background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 10px; }
        button { padding: 10px 20px; font-size: 16px; background: #ffd700; color: #000; border: none; border-radius: 8px; cursor: pointer; margin: 10px; }
        button:hover { background: #ffcc00; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ lang == 'ml' and 'ക്രിപ്റ്റോ രാജാവ്' or 'Crypto King' }}</h1>
        <div class="stats">
            👑 Level: {{ level }} | 💰 Coins: {{ "%.4f"|format(coins) }}<br>
            <div class="energy-bar"><div class="energy-fill" style="width: {{ energy }}%;"></div></div>
            ⚡ Energy: {{ energy }}/100
        </div>
        <div class="puzzle">
            <p>{{ lang == 'ml' and 'പസിൽ പരിഹരിച്ച് കോയിനുകൾ നേടൂ!' or 'Solve the Puzzle to Mine Coins!' }}</p>
            <div class="grid" id="grid"></div>
            <button onclick="newPuzzle()">New Puzzle</button>
            <button onclick="exit()">Exit</button>
        </div>
        <div class="message" id="message"></div>
        <div class="leaderboard">
            <h3>{{ lang == 'ml' and 'മികച്ച കളിക്കാർ' or 'Top Players' }}</h3>
            {% for player in leaderboard %}
                {{ loop.index }}. @{{ player[0] }} - {{ "%.4f"|format(player[1]) }} Coins<br>
            {% endfor %}
        </div>
    </div>
    <script>
        let tiles = [];
        let matched = 0;
        function newPuzzle() {
            fetch('/puzzle?user_id={{ user_id }}')
                .then(response => response.json())
                .then(data => {
                    tiles = data.tiles;
                    matched = 0;
                    renderPuzzle();
                });
        }
        function renderPuzzle() {
            const grid = document.getElementById('grid');
            grid.innerHTML = '';
            tiles.forEach((tile, i) => {
                const div = document.createElement('div');
                div.className = 'tile' + (tile.matched ? ' matched' : '');
                div.innerText = tile.hidden ? '?' : tile.value;
                div.onclick = () => clickTile(i);
                grid.appendChild(div);
            });
        }
        function clickTile(index) {
            fetch('/mine?user_id={{ user_id }}&tile=' + index, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('message').innerText = data.message;
                    if (data.success) {
                        tiles = data.tiles;
                        matched = data.matched;
                        renderPuzzle();
                        if (data.complete) setTimeout(() => location.reload(), 1000);
                    }
                });
        }
        function exit() { window.Telegram.WebApp.close(); }
        newPuzzle();  // Start with a puzzle
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
    c.execute("SELECT level, coins, energy, lang, username FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, "Player"))
        conn.commit()
        level, coins, energy, lang = 1, 0, 100, "en", "Player"
    else:
        level, coins, energy, lang, _ = user_data
    c.execute("SELECT username, coins FROM users ORDER BY coins DESC LIMIT 5")
    leaderboard = c.fetchall()
    return render_template_string(html_template, user_id=user_id, level=level, coins=coins, energy=energy, lang=lang, leaderboard=leaderboard)

@app.route('/puzzle')
def new_puzzle():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    # Generate a 3x3 puzzle with 3 pairs
    values = [1, 1, 2, 2, 3, 3] + [0] * 3  # 3 pairs + 3 blanks
    random.shuffle(values)
    tiles = [{"value": v, "hidden": True, "matched": False} for v in values]
    return jsonify({"tiles": tiles})

@app.route('/mine', methods=['POST'])
def mine_web():
    user_id = request.args.get('user_id')
    tile_index = int(request.args.get('tile', -1))
    c.execute("SELECT energy, coins, lang FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        return jsonify({"success": False, "message": "User not found"}), 404
    energy, coins, lang = user_data
    if energy < 10:
        message = "⚡ Energy Low! Wait or Boost!" if lang == "en" else "⚡ എനർജി കുറവാണ്! കാത്തിരിക്കുക അല്ലെങ്കിൽ ബൂസ്റ്റ് ചെയ്യുക!"
        return jsonify({"success": False, "message": message})

    # Simple puzzle logic (mocked for now)
    tiles = [{"value": v, "hidden": True, "matched": False} for v in ([1, 1, 2, 2, 3, 3] + [0] * 3)]
    random.shuffle(tiles)
    if tile_index >= 0 and tile_index < len(tiles):
        tiles[tile_index]["hidden"] = False
        matched = sum(1 for t in tiles if not t["hidden"] and t["value"] != 0)
        for i, t in enumerate(tiles):
            if not t["hidden"] and t["value"] != 0:
                for j, other in enumerate(tiles):
                    if i != j and not other["hidden"] and other["value"] == t["value"]:
                        tiles[i]["matched"] = tiles[j]["matched"] = True
        matched = sum(1 for t in tiles if t["matched"])
        if matched >= 6:  # All pairs matched
            coins_earned = random.uniform(0.01, 0.05)  # Bigger reward for solving
            c.execute("UPDATE users SET coins = coins + ?, energy = energy - 10, level = level + 1 WHERE user_id = ?", (coins_earned, user_id))
            conn.commit()
            message = f"🎉 Puzzle Solved! +{coins_earned:.4f} Coins!" if lang == "en" else f"🎉 പസിൽ പരിഹരിച്ചു! +{coins_earned:.4f} കോയിനുകൾ!"
            logger.info(f"User {user_id} solved puzzle, earned {coins_earned} coins")
            return jsonify({"success": True, "message": message, "tiles": tiles, "matched": matched, "complete": True})
        else:
            c.execute("UPDATE users SET energy = energy - 10 WHERE user_id = ?", (user_id,))
            conn.commit()
            message = "🔍 Tile Revealed! Keep going!" if lang == "en" else "🔍 ടൈൽ വെളിപ്പെടുത്തി! തുടരുക!"
            return jsonify({"success": True, "message": message, "tiles": tiles, "matched": matched, "complete": False})
    return jsonify({"success": False, "message": "Invalid tile"}), 400

# Bot command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Player"
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    # Only one button to start the Web App
    keyboard = [[InlineKeyboardButton("🎮 Start Mining", web_app=WebAppInfo(url=f"https://replit.com/@princephilip514/crypto={user_id}"))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👑 Crypto King: Solve Puzzles, Mine Coins!", reply_markup=reply_markup)
    logger.info(f"User {user_id} started the bot")

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
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True).start()

    # Background energy refill
    def refill_energy():
        while True:
            thread_conn = sqlite3.connect("users.db", check_same_thread=False)
            thread_c = thread_conn.cursor()
            try:
                thread_c.execute("UPDATE users SET energy = LEAST(energy + 10, 100) WHERE energy < 100")
                thread_conn.commit()
            except Exception as e:
                logger.error(f"Error in refill_energy: {e}")
            finally:
                thread_conn.close()
            time.sleep(600)  # Refill 10 energy every 10 mins
    threading.Thread(target=refill_energy, daemon=True).start()

    application.run_polling()

if __name__ == "__main__":
    main()