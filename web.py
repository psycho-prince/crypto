import os
import sqlite3
import logging
from flask import Flask, request, render_template_string, jsonify
import random
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, coins REAL DEFAULT 0, energy INTEGER DEFAULT 100, level INTEGER DEFAULT 1, lang TEXT DEFAULT 'en')")
conn.commit()

# Flask app
app = Flask(__name__)

# HTML template with puzzle game
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
        <h1>Crypto King</h1>
        <div class="stats">
            👑 Level: {{ level }} | 💰 Coins: {{ "%.4f"|format(coins) }}<br>
            <div class="energy-bar"><div class="energy-fill" style="width: {{ energy }}%;"></div></div>
            ⚡ Energy: {{ energy }}/100
        </div>
        <div class="puzzle">
            <p>Solve the Puzzle to Mine Coins!</p>
            <div class="grid" id="grid"></div>
            <button onclick="newPuzzle()">New Puzzle</button>
            <button onclick="exit()">Exit</button>
        </div>
        <div class="message" id="message"></div>
        <div class="leaderboard">
            <h3>Top Players</h3>
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
    logger.info(f"WebApp request for user_id: {user_id}")
    if not user_id:
        logger.error("No user_id provided")
        return "User ID required", 400
    c.execute("SELECT level, coins, energy, username FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, "Player"))
        conn.commit()
        level, coins, energy = 1, 0, 100
    else:
        level, coins, energy, _ = user_data
    c.execute("SELECT username, coins FROM users ORDER BY coins DESC LIMIT 5")
    leaderboard = c.fetchall()
    logger.info(f"Serving UI for user_id: {user_id}")
    return render_template_string(html_template, user_id=user_id, level=level, coins=coins, energy=energy, leaderboard=leaderboard)

@app.route('/puzzle')
def new_puzzle():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    values = [1, 1, 2, 2, 3, 3] + [0] * 3  # 3 pairs + 3 blanks
    random.shuffle(values)
    tiles = [{"value": v, "hidden": True, "matched": False} for v in values]
    return jsonify({"tiles": tiles})

@app.route('/mine', methods=['POST'])
def mine_web():
    user_id = request.args.get('user_id')
    tile_index = int(request.args.get('tile', -1))
    c.execute("SELECT energy, coins FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        return jsonify({"success": False, "message": "User not found"}), 404
    energy, coins = user_data
    if energy < 10:
        return jsonify({"success": False, "message": "⚡ Energy Low! Wait or Boost!"})
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
            coins_earned = random.uniform(0.01, 0.05)
            c.execute("UPDATE users SET coins = coins + ?, energy = energy - 10, level = level + 1 WHERE user_id = ?", (coins_earned, user_id))
            conn.commit()
            message = f"🎉 Puzzle Solved! +{coins_earned:.4f} Coins!"
            logger.info(f"User {user_id} solved puzzle, earned {coins_earned} coins")
            return jsonify({"success": True, "message": message, "tiles": tiles, "matched": matched, "complete": True})
        else:
            c.execute("UPDATE users SET energy = energy - 10 WHERE user_id = ?", (user_id,))
            conn.commit()
            message = "🔍 Tile Revealed! Keep going!"
            return jsonify({"success": True, "message": message, "tiles": tiles, "matched": matched, "complete": False})
    return jsonify({"success": False, "message": "Invalid tile"}), 400

# Energy refill loop
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
        time.sleep(600)

if __name__ == "__main__":
    threading.Thread(target=refill_energy, daemon=True).start()
    logger.info("Starting Flask on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)