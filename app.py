import eventlet
eventlet.monkey_patch()  # Must be the first import

import os
import sqlite3
import logging
import asyncio
from datetime import datetime
import datetime as dt
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO, join_room, emit
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler, ChosenInlineResultHandler, ContextTypes
from telegram.error import TelegramError
from dotenv import load_dotenv
import uuid
import json
import requests
from functools import wraps
import time
import signal
import sys
from sqlite3 import Error
import retrying

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = "https://crypto-king-v2.onrender.com/webhook"

# Set up logging with GMT+5:30 timezone
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.Formatter.converter = lambda *args: dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).timetuple()
logger = logging.getLogger(__name__)

# Initialize Flask app and SocketIO
app = Flask(__name__, template_folder='templates', static_folder=None)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=10, ping_interval=5, reconnection=True, reconnection_attempts=3)

# Rate limiting dictionary
RATE_LIMIT = 1  # 1 request per second per user
last_request = {}

# Database connection pool
class DatabasePool:
    def __init__(self, db_file):
        self.db_file = db_file
        self.connection = None

    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            return self.connection
        except Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self):
        if self.connection:
            self.connection.close()

db_pool = DatabasePool('games.db')

# Database initialization
def init_db():
    conn = db_pool.connect()
    try:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            language_code TEXT,
            wins INTEGER DEFAULT 0,
            last_room_id TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS games (
            room_id TEXT PRIMARY KEY,
            players TEXT,
            usernames TEXT,
            board TEXT,
            current_turn TEXT,
            status TEXT,
            created_at TIMESTAMP,
            winner INTEGER
        )''')
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()

init_db()

# Rate limiting decorator
def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        current_time = time.time()
        if user_id in last_request:
            if current_time - last_request[user_id] < RATE_LIMIT:
                return jsonify({"error": "Rate limit exceeded. Please wait."}), 429
        last_request[user_id] = current_time
        return f(*args, **kwargs)
    return decorated_function

# Chain Reaction Game Logic
class ChainReactionGame:
    def __init__(self, room_id, host_id, host_username, board=None):
        self.room_id = room_id
        self.players = [host_id]
        self.usernames = [host_username]
        self.board = board if board else [[0 for _ in range(9)] for _ in range(6)]
        self.current_turn = host_id
        self.status = "not_started"
        self.winner = None
        self.callbacks = {"game_status_change": [], "destroy": [], "chain_reaction": []}
        self.max_players = 8  # Increased to match BuddyMattEnt game

    def add_player(self, player_id, username):
        if len(self.players) >= self.max_players or player_id in self.players:
            return False
        self.players.append(player_id)
        self.usernames.append(username)
        if len(self.players) >= 2 and self.status == "not_started":
            self.status = "in_progress"
        self._trigger_callback("game_status_change")
        return True

    def make_move(self, player_id, row, col):
        if self.status != "in_progress" or player_id != self.current_turn:
            return False

        player = self.players.index(player_id) + 1
        if not (0 <= row < 6 and 0 <= col < 9):
            return False

        self.board[row][col] = (self.board[row][col] % 10) + (10 * player) + 1
        chain_reactions = self._process_chain_reaction(row, col, player)

        scores = [0] * len(self.players)
        for p in range(len(self.players)):
            scores[p] = sum(1 for r in range(6) for c in range(9) if self.board[r][c] > 0 and self.board[r][c] // 10 == (p + 1))

        active_players = sum(1 for score in scores if score > 0)
        if active_players <= 1 and len(self.players) > 1:
            self.status = "finished"
            for p in range(len(self.players)):
                if scores[p] > 0:
                    self.winner = p + 1
                    self._update_wins(self.players[p])
                    break

        if self.status == "in_progress":
            current_idx = self.players.index(player_id)
            next_idx = (current_idx + 1) % len(self.players)
            self.current_turn = self.players[next_idx]

        self._trigger_callback("game_status_change")
        if chain_reactions:
            self._trigger_callback("chain_reaction", chain_reactions)
        return True

    def _update_wins(self, winner_id):
        conn = db_pool.connect()
        try:
            c = conn.cursor()
            c.execute("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (winner_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update wins for user {winner_id}: {e}")
        finally:
            conn.close()

    def _process_chain_reaction(self, row, col, player):
        reactions = []
        rows, cols = 6, 9
        critical_mass = 4
        if (row == 0 or row == rows - 1) and (col == 0 or col == cols - 1):
            critical_mass = 2
        elif row == 0 or row == rows - 1 or col == 0 or col == cols - 1:
            critical_mass = 3

        atoms = self.board[row][col] % 10
        if atoms < critical_mass:
            return reactions

        reactions.append({"row": row, "col": col, "player": player})
        self.board[row][col] = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                self.board[nr][nc] = (self.board[nr][nc] % 10) + (10 * player) + 1
                sub_reactions = self._process_chain_reaction(nr, nc, player)
                reactions.extend(sub_reactions)
        return reactions

    def on(self, event, callback):
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _trigger_callback(self, event, data=None):
        for callback in self.callbacks.get(event, []):
            callback(data)

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "players": self.players,
            "usernames": self.usernames,
            "board": self.board,
            "current_turn": self.current_turn,
            "status": self.status,
            "winner": self.winner
        }

# Game Server to Manage Rooms
class GameServer:
    def __init__(self):
        self.rooms = {}

    def create_room(self, host_id, host_username):
        room_id = str(uuid.uuid4())
        game = ChainReactionGame(room_id, host_id, host_username)
        self.rooms[room_id] = game

        conn = db_pool.connect()
        try:
            c = conn.cursor()
            c.execute("INSERT INTO games (room_id, players, usernames, board, current_turn, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (room_id, json.dumps([host_id]), json.dumps([host_username]), json.dumps(game.board), host_id, "not_started", datetime.now().isoformat()))
            c.execute("UPDATE users SET last_room_id = ? WHERE user_id = ?", (room_id, host_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to create room {room_id} in database: {e}")
            return None
        finally:
            conn.close()
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

    conn = db_pool.connect()
    try:
        c = conn.cursor()
        c.execute("SELECT username, last_room_id FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            c.execute("INSERT INTO users (user_id, username, full_name, language_code) VALUES (?, ?, ?, ?)",
                      (user_id, username, username, "en"))
            conn.commit()
        else:
            username = user[0]
            if not room_id and user[1]:
                room_id = user[1]
    except Exception as e:
        logger.error(f"Failed to fetch user {user_id} from database: {e}")
        return jsonify({"error": "Database error"}), 500
    finally:
        conn.close()

    game_data = None
    if room_id:
        game = game_server.get_room(room_id)
        if game:
            game_data = game.to_dict()
        else:
            conn = db_pool.connect()
            try:
                c = conn.cursor()
                c.execute("SELECT * FROM games WHERE room_id = ?", (room_id,))
                game_row = c.fetchone()
                if game_row:
                    game = ChainReactionGame(
                        room_id=game_row[0],
                        host_id=json.loads(game_row[1])[0],
                        host_username=json.loads(game_row[2])[0],
                        board=json.loads(game_row[3])
                    )
                    game.players = json.loads(game_row[1])
                    game.usernames = json.loads(game_row[2])
                    game.current_turn = game_row[4]
                    game.status = game_row[5]
                    game.winner = game_row[7]
                    game_server.rooms[room_id] = game
                    game_data = game.to_dict()
            except Exception as e:
                logger.error(f"Failed to load game {room_id} from database: {e}")
            finally:
                conn.close()

    return render_template('index.html', user_id=user_id, username=username, room_id=room_id, game_data=game_data)

@app.route('/start_game', methods=['POST'])
@rate_limit
def start_game():
    user_id = request.args.get('user_id')
    username = request.args.get('username')
    if not user_id or not username:
        return jsonify({"error": "Missing user_id or username"}), 400

    game = game_server.create_room(user_id, username)
    if not game:
        return jsonify({"error": "Failed to create game"}), 500
    game_url = f"https://crypto-king-v2.onrender.com/?user_id={user_id}&username={username}&room_id={game.room_id}"
    return jsonify({"room_id": game.room_id, "game_url": game_url, "game_data": game.to_dict()})

@app.route('/make_move', methods=['POST'])
@rate_limit
def make_move():
    user_id = request.args.get('user_id')
    room_id = request.args.get('room_id')
    try:
        row = int(request.args.get('row'))
        col = int(request.args.get('col'))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid row or col"}), 400

    if not user_id or not room_id:
        return jsonify({"error": "Missing user_id or room_id"}), 400

    game = game_server.get_room(room_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404

    if game.make_move(user_id, row, col):
        conn = db_pool.connect()
        try:
            c = conn.cursor()
            c.execute("UPDATE games SET board = ?, current_turn = ?, status = ?, winner = ? WHERE room_id = ?",
                      (json.dumps(game.board), game.current_turn, game.status, game.winner, room_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update game {room_id} in database: {e}")
            return jsonify({"error": "Database error"}), 500
        finally:
            conn.close()
        socketio.emit('game_update', {"room_id": room_id, "game_data": game.to_dict()}, room=room_id)
        return jsonify(game.to_dict())
    else:
        return jsonify({"error": "Invalid move"}), 400

@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    conn = db_pool.connect()
    try:
        c = conn.cursor()
        c.execute("SELECT username, wins FROM users ORDER BY wins DESC LIMIT 10")
        leaders = c.fetchall()
        return jsonify([{"username": username, "wins": wins} for username, wins in leaders])
    except Exception as e:
        logger.error(f"Failed to fetch leaderboard: {e}")
        return jsonify({"error": "Failed to fetch leaderboard"}), 500
    finally:
        conn.close()

@app.route('/health', methods=['GET'])
def health():
    try:
        conn = db_pool.connect()
        c = conn.cursor()
        c.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "healthy", "message": "Application and database are running"})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "message": str(e)}), 500

@app.route('/debug', methods=['GET'])
def debug():
    return "Chain Reaction Game v1.0 - Flask is running!"

# Webhook Route for Telegram
@app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        update = Update.de_json(request.get_json(), bot_app.bot)
        await bot_app.process_update(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": "Webhook error"}), 500

# WebSocket Events
@socketio.on('join_game')
def on_join_game(data):
    room_id = data['room_id']
    user_id = data['user_id']
    username = data['username']
    logger.info(f"User {user_id} ({username}) attempting to join room {room_id}")
    join_room(room_id)

    game = game_server.get_room(room_id)
    if not game:
        # Try to load from database
        conn = db_pool.connect()
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM games WHERE room_id = ?", (room_id,))
            game_row = c.fetchone()
            if game_row:
                game = ChainReactionGame(
                    room_id=game_row[0],
                    host_id=json.loads(game_row[1])[0],
                    host_username=json.loads(game_row[2])[0],
                    board=json.loads(game_row[3])
                )
                game.players = json.loads(game_row[1])
                game.usernames = json.loads(game_row[2])
                game.current_turn = game_row[4]
                game.status = game_row[5]
                game.winner = game_row[7]
                game_server.rooms[room_id] = game
            else:
                emit('join_error', {"error": "Game not found"}, to=user_id)
                logger.error(f"Game {room_id} not found in database")
                return
        except Exception as e:
            logger.error(f"Failed to load game {room_id} from database: {e}")
            emit('join_error', {"error": "Database error"}, to=user_id)
            return
        finally:
            conn.close()

    if game and game.add_player(user_id, username):
        conn = db_pool.connect()
        try:
            c = conn.cursor()
            c.execute("UPDATE games SET players = ?, usernames = ?, status = ? WHERE room_id = ?",
                      (json.dumps(game.players), json.dumps(game.usernames), game.status, room_id))
            c.execute("UPDATE users SET last_room_id = ? WHERE user_id = ?", (room_id, user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update game {room_id} or user {user_id} in database: {e}")
            emit('join_error', {"error": "Database error"}, to=user_id)
            return
        finally:
            conn.close()

        emit('game_start', game.to_dict(), room=room_id)
        emit('player_joined', {"username": username}, room=room_id)
        logger.info(f"User {user_id} ({username}) successfully joined room {room_id}")
    else:
        emit('join_error', {"error": "Unable to join game"}, to=user_id)
        logger.error(f"User {user_id} ({username}) failed to join room {room_id}")

@socketio.on('game_update')
def on_game_update(data):
    room_id = data['room_id']
    emit('game_update', data, room=room_id)

@socketio.on('chain_reaction')
def on_chain_reaction(data):
    emit('chain_reaction', data, room=data['room_id'])

@socketio.on('connect')
def on_connect():
    logger.info(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('connect_error')
def on_connect_error(data):
    logger.error(f"Socket.IO connect error: {data}")

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    language_code = user.language_code or "en"

    conn = db_pool.connect()
    try:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, username, full_name, language_code) VALUES (?, ?, ?, ?)",
                  (user_id, username, full_name, language_code))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to upsert user {user_id} in database: {e}")
    finally:
        conn.close()

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

    conn = db_pool.connect()
    try:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, username, full_name, language_code) VALUES (?, ?, ?, ?)",
                  (user_id, username, f"{user.first_name} {user.last_name or ''}".strip(), language_code))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to upsert user {user_id} in database: {e}")
    finally:
        conn.close()

    results = [
        {
            "type": "article",
            "id": "create_game",
            "title": "Start a Chain Reaction Game",
            "description": "Play a 6x9 Chain Reaction game with friends!",
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

@retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
async def update_inline_message(context, inline_message_id, message_text, reply_markup):
    try:
        await context.bot.edit_message_text(
            chat_id=None,
            message_id=inline_message_id,
            inline_message_id=inline_message_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        logger.info(f"Updated inline message {inline_message_id} with text: {message_text}")
    except TelegramError as e:
        logger.error(f"Failed to update inline message {inline_message_id}: {e}")
        raise

async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chosen_inline_result.from_user
    user_id = str(user.id)
    username = user.username or user.first_name
    result_id = update.chosen_inline_result.result_id
    inline_message_id = update.chosen_inline_result.inline_message_id

    if result_id == "create_game":
        game = game_server.create_room(user_id, username)
        if not game:
            await update_inline_message(
                context,
                inline_message_id,
                "Failed to create game. Please try again.",
                InlineKeyboardMarkup([])
            )
            return

        game_url = f"https://crypto-king-v2.onrender.com/?user_id={user_id}&username={username}&room_id={game.room_id}"
        logger.info(f"Created game for user {user_id} ({username}) with room_id {game.room_id}, URL: {game_url}")

        message_text = f"{username} started a Chain Reaction game! Join now!"
        keyboard = [[InlineKeyboardButton("Join", web_app=WebAppInfo(url=game_url))]]
        try:
            await update_inline_message(
                context,
                inline_message_id,
                message_text,
                InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to update inline message {inline_message_id} after retries: {e}")
            return

        async def update_message():
            if game.status == "not_started":
                message_text = f"{username} started a Chain Reaction game! Join now!"
                keyboard = [[InlineKeyboardButton("Join", web_app=WebAppInfo(url=game_url))]]
            elif game.status == "in_progress":
                message_text = f"Chain Reaction game in progress: {', '.join(game.usernames)}"
                keyboard = [[InlineKeyboardButton("Watch", web_app=WebAppInfo(url=game_url))]]
            elif game.status == "finished":
                winner = game.usernames[game.winner - 1]
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
                await update_inline_message(
                    context,
                    inline_message_id,
                    message_text,
                    InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Failed to update inline message {inline_message_id} for status {game.status}: {e}")

        game.on("game_status_change", lambda: asyncio.create_task(update_message()))

# Initialize Telegram Bot with Webhooks
bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(lambda update, context: update.callback_query.answer()))
bot_app.add_handler(InlineQueryHandler(inline_query))
bot_app.add_handler(ChosenInlineResultHandler(chosen_inline_result))

# Retry logic for setting webhook
@retrying.retry(stop_max_attempt_number=3, wait_fixed=2000)
async def set_webhook_with_retry():
    await bot_app.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

# Set webhook during app initialization
async def initialize_webhook():
    try:
        await set_webhook_with_retry()
    except Exception as e:
        logger.error(f"Failed to set webhook after retries: {e}")

# Run webhook setup
loop = asyncio.get_event_loop()
loop.run_until_complete(initialize_webhook())

# Graceful shutdown
def shutdown_handler(signum, frame):
    logger.info("Received shutdown signal. Shutting down gracefully...")
    db_pool.close()
    socketio.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# Start the bot
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
