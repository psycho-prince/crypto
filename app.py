import eventlet
eventlet.monkey_patch()  # Must be the first import

import os
import sqlite3
import logging
import threading
import asyncio
from datetime import datetime
import datetime as dt
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO, join_room, emit
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler, ChosenInlineResultHandler, ContextTypes
from dotenv import load_dotenv
import uuid
import json

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Set up logging with GMT+5:30 timezone
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.Formatter.converter = lambda *args: dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).timetuple()
logger = logging.getLogger(__name__)

# Initialize Flask app and SocketIO
app = Flask(__name__, template_folder='templates', static_folder=None)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Flag to prevent multiple bot polling instances
bot_polling_started = False

# Database initialization
def init_db():
    with sqlite3.connect('games.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            language_code TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS games (
            room_id TEXT PRIMARY KEY,
            player1_id TEXT,
            player2_id TEXT,
            board TEXT,
            current_turn TEXT,
            status TEXT,
            created_at TIMESTAMP,
            winner INTEGER
        )''')
        conn.commit()
    logger.info("Database initialized successfully")

# Call init_db() at module level to ensure it runs when gunicorn imports the app
init_db()

# Chain Reaction Game Logic
class ChainReactionGame:
    def __init__(self, room_id, host_id, board=None):
        self.room_id = room_id
        self.host_id = host_id
        self.opponent_id = None
        self.board = board if board else [[0 for _ in range(9)] for _ in range(6)]  # 6x9 grid
        self.current_turn = host_id
        self.status = "not_started"  # not_started, in_progress, finished
        self.winner = None
        self.callbacks = {"game_status_change": [], "destroy": []}

    def add_player(self, player_id):
        if self.opponent_id is None and player_id != self.host_id:
            self.opponent_id = player_id
            self.status = "in_progress"
            self._trigger_callback("game_status_change")
            return True
        return False

    def make_move(self, player_id, row, col):
        if self.status != "in_progress" or player_id != self.current_turn:
            return False

        # Determine player number (1 for host, 2 for opponent)
        player = 1 if player_id == self.host_id else 2
        if not (0 <= row < 6 and 0 <= col < 9):
            return False

        # Add atom to the cell
        self.board[row][col] = (self.board[row][col] % 10) + (10 * player) + 1
        self._process_chain_reaction(row, col, player)

        # Update scores and check game over
        player1_cells = sum(1 for r in range(6) for c in range(9) if self.board[r][c] > 0 and self.board[r][c] // 10 == 1)
        player2_cells = sum(1 for r in range(6) for c in range(9) if self.board[r][c] > 0 and self.board[r][c] // 10 == 2)

        if player1_cells == 0 and player2_cells > 0 and self.opponent_id is not None:
            self.status = "finished"
            self.winner = 2
        elif player2_cells == 0 and player1_cells > 0 and self.opponent_id is not None:
            self.status = "finished"
            self.winner = 1

        # Switch turns if game is still in progress
        if self.status == "in_progress":
            self.current_turn = self.opponent_id if player_id == self.host_id else self.host_id

        self._trigger_callback("game_status_change")
        return True

    def _process_chain_reaction(self, row, col, player):
        rows, cols = 6, 9
        # Calculate critical mass
        critical_mass = 4  # Middle
        if (row == 0 or row == rows - 1) and (col == 0 or col == cols - 1):
            critical_mass = 2  # Corner
        elif row == 0 or row == rows - 1 or col == 0 or col == cols - 1:
            critical_mass = 3  # Edge

        atoms = self.board[row][col] % 10
        if atoms < critical_mass:
            return

        # Explode: reset cell and distribute atoms
        self.board[row][col] = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                self.board[nr][nc] = (self.board[nr][nc] % 10) + (10 * player) + 1
                self._process_chain_reaction(nr, nc, player)

    def on(self, event, callback):
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _trigger_callback(self, event):
        for callback in self.callbacks.get(event, []):
            callback()

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "host_id": self.host_id,
            "opponent_id": self.opponent_id,
            "board": self.board,
            "current_turn": self.current_turn,
            "status": self.status,
            "winner": self.winner
        }

# Game Server to Manage Rooms
class GameServer:
    def __init__(self):
        self.rooms = {}

    def create_room(self, host_id):
        room_id = str(uuid.uuid4())
        game = ChainReactionGame(room_id, host_id)
        self.rooms[room_id] = game

        # Save to database
        with sqlite3.connect('games.db') as conn:
            c = conn.cursor()
            c.execute("INSERT INTO games (room_id, player1_id, board, current_turn, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (room_id, host_id, json.dumps(game.board), host_id, "not_started", datetime.now().isoformat()))
            conn.commit()

        return game

    def get_room(self, room_id):
        return self.rooms.get(room_id)

# Flask Routes
game_server = GameServer()

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

    with sqlite3.connect('games.db') as conn:
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            c.execute("INSERT INTO users (user_id, username, full_name, language_code) VALUES (?, ?, ?, ?)",
                      (user_id, username, username, "en"))
            conn.commit()
        else:
            username = user[0]

    game_data = None
    if room_id:
        game = game_server.get_room(room_id)
        if game:
            game_data = game.to_dict()

    return render_template('index.html', user_id=user_id, username=username, room_id=room_id, game_data=game_data)

@app.route('/start_game', methods=['POST'])
def start_game():
    user_id = request.args.get('user_id')
    username = request.args.get('username')
    if not user_id or not username:
        return jsonify({"error": "Missing user_id or username"}), 400

    game = game_server.create_room(user_id)
    game_url = f"https://crypto-king-v2.onrender.com/?user_id={user_id}&username={username}&room_id={game.room_id}"
    return jsonify({"room_id": game.room_id, "game_url": game_url, "game_data": game.to_dict()})

@app.route('/make_move', methods=['POST'])
def make_move():
    user_id = request.args.get('user_id')
    room_id = request.args.get('room_id')
    row = int(request.args.get('row'))
    col = int(request.args.get('col'))

    if not user_id or not room_id:
        return jsonify({"error": "Missing user_id or room_id"}), 400

    game = game_server.get_room(room_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404

    if game.make_move(user_id, row, col):
        # Update database
        with sqlite3.connect('games.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE games SET board = ?, current_turn = ?, status = ?, winner = ? WHERE room_id = ?",
                      (json.dumps(game.board), game.current_turn, game.status, game.winner, room_id))
            conn.commit()
        return jsonify(game.to_dict())
    else:
        return jsonify({"error": "Invalid move"}), 400

@app.route('/debug', methods=['GET'])
def debug():
    return "Chain Reaction Game v1.0 - Flask is running!"

# WebSocket Events
@socketio.on('join_game')
def on_join_game(data):
    room_id = data['room_id']
    user_id = data['user_id']
    join_room(room_id)

    game = game_server.get_room(room_id)
    if game and game.add_player(user_id):
        # Update database
        with sqlite3.connect('games.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE games SET player2_id = ?, status = ? WHERE room_id = ?",
                      (user_id, "in_progress", room_id))
            conn.commit()
        emit('game_start', game.to_dict(), room=room_id)

@socketio.on('game_update')
def on_game_update(data):
    room_id = data['room_id']
    emit('game_update', data, room=room_id)

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    language_code = user.language_code or "en"

    # Upsert user in database
    with sqlite3.connect('games.db') as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, username, full_name, language_code) VALUES (?, ?, ?, ?)",
                  (user_id, username, full_name, language_code))
        conn.commit()

    keyboard = [
        [InlineKeyboardButton("Play Chain Reaction", switch_inline_query_current_chat="")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Welcome, {username}! 🎮\nStart a Chain Reaction game!",
        reply_markup=reply_markup
    )
    logger.info(f"User {user_id} ({username}) started bot")

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    user = update.inline_query.from_user
    user_id = str(user.id)
    username = user.username or user.first_name
    language_code = user.language_code or "en"

    # Upsert user
    with sqlite3.connect('games.db') as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, username, full_name, language_code) VALUES (?, ?, ?, ?)",
                  (user_id, username, f"{user.first_name} {user.last_name or ''}".strip(), language_code))
        conn.commit()

    results = [
        {
            "type": "article",
            "id": "create_game",
            "title": "Start a Chain Reaction Game",
            "description": "Play a 6x9 Chain Reaction game with a friend!",
            "input_message_content": {
                "message_text": f"{username} is creating a Chain Reaction game...",
                "parse_mode": "Markdown"
            },
            "reply_markup": {
                "inline_keyboard": [[{"text": "Waiting...", "callback_data": "creating-room"}]]
            }
        }
    ]

    await update.inline_query.answer(results, cache_time=0)

async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chosen_inline_result.from_user
    user_id = str(user.id)
    username = user.username or user.first_name
    result_id = update.chosen_inline_result.result_id
    inline_message_id = update.chosen_inline_result.inline_message_id

    if result_id == "create_game":
        game = game_server.create_room(user_id)
        game_url = f"https://crypto-king-v2.onrender.com/?user_id={user_id}&username={username}&room_id={game.room_id}"

        # Update message with join button
        async def update_message():
            if game.status == "not_started":
                message_text = f"{username} started a Chain Reaction game! Join now!"
                keyboard = [[InlineKeyboardButton("Join", web_app=WebAppInfo(url=game_url))]]
            elif game.status == "in_progress":
                message_text = f"Chain Reaction game in progress: {username} vs {game.opponent_id}"
                keyboard = [[InlineKeyboardButton("Watch", web_app=WebAppInfo(url=game_url))]]
            elif game.status == "finished":
                winner = username if game.winner == 1 else game.opponent_id
                message_text = f"Game finished! {winner} wins!"
                keyboard = [
                    [InlineKeyboardButton("Play Again", switch_inline_query_current_chat="")],
                    [InlineKeyboardButton("Play Another", switch_inline_query_chosen_chat={
                        "query": "",
                        "allow_bot_chats": False,
                        "allow_channel_chats": True,
                        "allow_user_chats": True,
                        "allow_group_chats": True
                    })]
                ]
            else:
                return

            try:
                await context.bot.edit_message_text(
                    chat_id=None,
                    message_id=inline_message_id,
                    inline_message_id=inline_message_id,
                    text=message_text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Failed to update inline message: {e}")

        # Call update_message immediately to show the "Join" button
        await update_message()
        # Also set up the callback for future status changes
        game.on("game_status_change", lambda: asyncio.create_task(update_message()))

# Function to run Telegram bot polling in a separate thread
def run_bot():
    global bot_polling_started
    if bot_polling_started:
        logger.warning("Bot polling already started, skipping duplicate instance")
        return

    bot_polling_started = True
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initialize the bot
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(lambda update, context: update.callback_query.answer()))
    bot_app.add_handler(InlineQueryHandler(inline_query))
    bot_app.add_handler(ChosenInlineResultHandler(chosen_inline_result))
    logger.info("Starting bot polling...")

    # Run the polling in the new event loop
    loop.run_until_complete(bot_app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True))

# Start the Telegram bot in a separate thread
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()
