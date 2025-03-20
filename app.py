import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO, join_room, emit
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import threading
import uuid

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app and SocketIO
app = Flask(__name__, template_folder='templates', static_folder=None)
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key
socketio = SocketIO(app, cors_allowed_origins="*")

# Game rooms dictionary to store active games
game_rooms = {}

# Database initialization
def init_db():
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            coins INTEGER,
            energy INTEGER,
            total_taps INTEGER,
            referrals INTEGER,
            last_refill TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS games (
            room_id TEXT PRIMARY KEY,
            player1_id TEXT,
            player2_id TEXT,
            player1_coins INTEGER DEFAULT 0,
            player2_coins INTEGER DEFAULT 0,
            mode TEXT,
            start_time TIMESTAMP,
            duration INTEGER,
            status TEXT
        )''')
        conn.commit()

# Refill energy based on elapsed time
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
                new_energy = min(100, energy + int(elapsed_minutes * 2))
                c.execute("UPDATE users SET energy = ?, last_refill = ? WHERE user_id = ?",
                          (new_energy, now.isoformat(), user_id))
            else:
                c.execute("UPDATE users SET energy = 100, last_refill = ? WHERE user_id = ?",
                          (datetime.now().isoformat(), user_id))
        conn.commit()

# Flask Routes
@app.route('/', methods=['GET'])
def index():
    user_id = request.args.get('user_id')
    username = request.args.get('username', 'Unknown')
    room_id = request.args.get('room_id')
    logger.info(f"Accessing / with user_id: {user_id}, username: {username}, room_id: {room_id}")
    
    if not user_id:
        user_id = "test_user"
        username = "Test User"
        logger.warning("No user_id provided, using test_user for debugging")
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT coins, energy, username, total_taps, referrals FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            c.execute("INSERT INTO users (user_id, username, coins, energy, total_taps, referrals, last_refill) VALUES (?, ?, 0, 100, 0, 0, ?)",
                      (user_id, username, datetime.now().isoformat()))
            conn.commit()
            coins, energy, username, total_taps, referrals = 0, 100, username, 0, 0
        else:
            coins, energy, stored_username, total_taps, referrals = user
            username = stored_username or username
            refill_energy(user_id)
            c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            c.execute("SELECT coins, energy, total_taps, referrals FROM users WHERE user_id = ?", (user_id,))
            coins, energy, total_taps, referrals = c.fetchone()
    
    c.execute("SELECT username, coins FROM users ORDER BY coins DESC LIMIT 5")
    leaderboard = c.fetchall()

    game_data = None
    if room_id:
        c.execute("SELECT * FROM games WHERE room_id = ? AND status = 'active'", (room_id,))
        game_data = c.fetchone()
        if game_data:
            game_data = {
                'room_id': game_data[0],
                'player1_id': game_data[1],
                'player2_id': game_data[2],
                'player1_coins': game_data[3],
                'player2_coins': game_data[4],
                'mode': game_data[5],
                'duration': game_data[7]
            }

    return render_template('index.html', coins=coins, energy=energy, user_id=user_id, username=username,
                           total_taps=total_taps, referrals=referrals, leaderboard=leaderboard,
                           room_id=room_id, game_data=game_data)

@app.route('/mine', methods=['POST'])
def mine():
    user_id = request.args.get('user_id')
    room_id = request.args.get('room_id')
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT coins, energy, total_taps FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        coins, energy, total_taps = user
        if energy < 1:
            return jsonify({"error": "Not enough energy"}), 400
        
        c.execute("UPDATE users SET coins = coins + 1, energy = energy - 1, total_taps = total_taps + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        c.execute("SELECT coins, energy, total_taps FROM users WHERE user_id = ?", (user_id,))
        coins, energy, total_taps = c.fetchone()

        if room_id:
            c.execute("SELECT player1_id, player2_id, player1_coins, player2_coins FROM games WHERE room_id = ? AND status = 'active'", (room_id,))
            game = c.fetchone()
            if game:
                player1_id, player2_id, player1_coins, player2_coins = game
                if user_id == player1_id:
                    player1_coins += 1
                    c.execute("UPDATE games SET player1_coins = ? WHERE room_id = ?", (player1_coins, room_id))
                elif user_id == player2_id:
                    player2_coins += 1
                    c.execute("UPDATE games SET player2_coins = ? WHERE room_id = ?", (player2_coins, room_id))
                conn.commit()
                socketio.emit('game_update', {
                    'room_id': room_id,
                    'player1_coins': player1_coins,
                    'player2_coins': player2_coins
                }, room=room_id)
    
    return jsonify({"coins": coins, "energy": energy, "total_taps": total_taps})

@app.route('/refer', methods=['POST'])
def refer():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET referrals = referrals + 1, coins = coins + 50 WHERE user_id = ?",
                  (user_id,))
        conn.commit()
        c.execute("SELECT coins, referrals FROM users WHERE user_id = ?", (user_id,))
        coins, referrals = c.fetchone()
    
    return jsonify({"coins": coins, "referrals": referrals})

@app.route('/create_game', methods=['POST'])
def create_game():
    user_id = request.args.get('user_id')
    username = request.args.get('username')
    mode = request.args.get('mode', 'rapid')
    duration = 60 if mode == 'rapid' else 30  # 60 seconds for rapid, 30 for blitz
    
    room_id = str(uuid.uuid4())
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("INSERT INTO games (room_id, player1_id, mode, start_time, duration, status) VALUES (?, ?, ?, ?, ?, 'waiting')",
                  (room_id, user_id, mode, datetime.now().isoformat(), duration))
        conn.commit()
    
    game_rooms[room_id] = {'player1_id': user_id, 'player2_id': None, 'mode': mode, 'duration': duration}
    return jsonify({"room_id": room_id})

@app.route('/debug', methods=['GET'])
def debug():
    return "Crypto King Mining Game v1.0 - Flask is running!"

# WebSocket Events
@socketio.on('join_game')
def on_join_game(data):
    room_id = data['room_id']
    user_id = data['user_id']
    join_room(room_id)
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT player1_id, player2_id, mode, duration, status FROM games WHERE room_id = ?", (room_id,))
        game = c.fetchone()
        if game and game[4] == 'waiting':
            player1_id, player2_id, mode, duration, status = game
            if user_id != player1_id and not player2_id:
                c.execute("UPDATE games SET player2_id = ?, status = 'active' WHERE room_id = ?",
                          (user_id, room_id))
                conn.commit()
                game_rooms[room_id]['player2_id'] = user_id
                emit('game_start', {
                    'room_id': room_id,
                    'player1_id': player1_id,
                    'player2_id': user_id,
                    'mode': mode,
                    'duration': duration
                }, room=room_id)

@socketio.on('game_timer')
def on_game_timer(data):
    room_id = data['room_id']
    remaining_time = data['remaining_time']
    if remaining_time <= 0:
        with sqlite3.connect('users.db') as conn:
            c = conn.cursor()
            c.execute("SELECT player1_id, player2_id, player1_coins, player2_coins FROM games WHERE room_id = ?", (room_id,))
            game = c.fetchone()
            if game:
                player1_id, player2_id, player1_coins, player2_coins = game
                winner = player1_id if player1_coins > player2_coins else player2_id
                c.execute("UPDATE games SET status = 'finished' WHERE room_id = ?", (room_id,))
                conn.commit()
                emit('game_end', {
                    'winner': winner,
                    'player1_coins': player1_coins,
                    'player2_coins': player2_coins
                }, room=room_id)
                if room_id in game_rooms:
                    del game_rooms[room_id]
    else:
        emit('timer_update', {'remaining_time': remaining_time}, room=room_id)

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or "Unknown"
    
    keyboard = [
        [InlineKeyboardButton("Play Solo", url=f"https://crypto-king-v2.onrender.com/?user_id={user_id}&username={username}")],
        [InlineKeyboardButton("Play Blitz (30s)", callback_data=f"create_game:blitz:{user_id}:{username}")],
        [InlineKeyboardButton("Play Rapid (60s)", callback_data=f"create_game:rapid:{user_id}:{username}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Welcome, {username}! 👑\nChoose a mode to play Crypto King!",
        reply_markup=reply_markup
    )
    logger.info(f"User {user_id} ({username}) started bot")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    action, mode, user_id, username = data
    
    if action == "create_game":
        room_id = str(uuid.uuid4())
        duration = 60 if mode == "rapid" else 30
        with sqlite3.connect('users.db') as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (user_id, username, coins, energy, total_taps, referrals, last_refill) VALUES (?, ?, 0, 100, 0, 0, ?)",
                      (user_id, username, datetime.now().isoformat()))
            c.execute("INSERT INTO games (room_id, player1_id, mode, start_time, duration, status) VALUES (?, ?, ?, ?, ?, 'waiting')",
                      (room_id, user_id, mode, datetime.now().isoformat(), duration))
            conn.commit()
        
        game_rooms[room_id] = {'player1_id': user_id, 'player2_id': None, 'mode': mode, 'duration': duration}
        invite_url = f"https://crypto-king-v2.onrender.com/?user_id={user_id}&username={username}&room_id={room_id}"
        keyboard = [[InlineKeyboardButton("Join Game", url=invite_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"{username} has started a {mode} game! Join the mining battle!",
            reply_markup=reply_markup
        )

# Function to run Flask app with SocketIO
def run_flask():
    init_db()
    logger.info("Starting Flask on 0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False)

# Function to run Telegram bot
def run_bot():
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Starting bot polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Run Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    # Run Telegram bot in the main thread
    run_bot()
