import sqlite3
import logging
from flask import Flask, request, render_template

app = Flask(__name__, template_folder='templates')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize database
def init_db():
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            coins INTEGER,
            energy INTEGER
        )''')
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
            c.execute("INSERT INTO users (user_id, coins, energy) VALUES (?, 0, 100)", (user_id,))
            conn.commit()
            coins, energy = 0, 100
        else:
            coins, energy = user
        # Refill energy (fixed LEAST issue)
        refill_energy(c, user_id)
        conn.commit()
    
    return render_template('index.html', coins=coins, energy=energy, user_id=user_id)

def refill_energy(cursor, user_id):
    try:
        # Replace LEAST with MIN or manual logic
        cursor.execute("UPDATE users SET energy = MIN(100, energy + 10) WHERE user_id = ?", (user_id,))
        # Alternative manual logic:
        # cursor.execute("UPDATE users SET energy = energy + 10 WHERE user_id = ? AND energy + 10 <= 100", (user_id,))
        # cursor.execute("UPDATE users SET energy = 100 WHERE user_id = ? AND energy > 100", (user_id,))
    except Exception as e:
        logger.error(f"Error in refill_energy: {str(e)}")

if __name__ == '__main__':
    init_db()  # Create DB on startup
    logger.info("Starting Flask on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
