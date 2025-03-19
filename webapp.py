import sqlite3
import logging
from flask import Flask, request, render_template, jsonify
from datetime import datetime

app = Flask(__name__, template_folder='templates', static_folder=None)  # Disable static folder
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize database
def init_db():
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            coins INTEGER,
            energy INTEGER,
            last_refill TIMESTAMP
        )''')
        conn.commit()

# Refill energy over time
def refill_energy(user_id):
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT energy, last_refill FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            energy, last_refill = result
            if last_refill:
                last_time = datetime.fromisoformat(last_refill)
                now = datetime.now()
                elapsed_minutes = (now - last_time).total_seconds() // 60
                new_energy = min(100, energy + int(elapsed_minutes * 2))  # 2 energy/min
                c.execute("UPDATE users SET energy = ?, last_refill = ? WHERE user_id = ?",
                          (new_energy, now.isoformat(), user_id))
            else:
                c.execute("UPDATE users SET energy = 100, last_refill = ? WHERE user_id = ?",
                          (datetime.now().isoformat(), user_id))
        conn.commit()

@app.route('/')
def index():
    user_id = request.args.get('user_id')
    if not user_id:
        logger.error("No user_id provided")
        return "Error: No user_id provided", 400
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT coins, energy FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            c.execute("INSERT INTO users (user_id, coins, energy, last_refill) VALUES (?, 0, 100, ?)",
                      (user_id, datetime.now().isoformat()))
            conn.commit()
            coins, energy = 0, 100
        else:
            coins, energy = user
            refill_energy(user_id)
            c.execute("SELECT coins, energy FROM users WHERE user_id = ?", (user_id,))
            coins, energy = c.fetchone()
    
    return render_template('index.html', coins=coins, energy=energy, user_id=user_id)

@app.route('/mine', methods=['POST'])
def mine():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT coins, energy FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        coins, energy = user
        if energy < 1:
            return jsonify({"error": "Not enough energy"}), 400
        
        c.execute("UPDATE users SET coins = coins + 1, energy = energy - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        c.execute("SELECT coins, energy FROM users WHERE user_id = ?", (user_id,))
        coins, energy = c.fetchone()
    
    return jsonify({"coins": coins, "energy": energy})

@app.route('/debug')
def debug():
    return "Crypto King Mining Game v1.0 - Flask is running!"

if __name__ == '__main__':
    init_db()
    logger.info("Starting Flask on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
