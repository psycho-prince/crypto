import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO, join_room, emit
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
            player1_score INTEGER DEFAULT 0,
            player2_score INTEGER DEFAULT 0,
            board TEXT,
            current_turn TEXT,
            mode TEXT,
            start_time TIMESTAMP,
            duration INTEGER,
            status TEXT
        )''')
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
        c.execute("SELECT coins, username, total_taps, referrals FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            c.execute("INSERT INTO users (user_id, username, coins, energy, total_taps, referrals, last_refill) VALUES (?, ?, 0, 100, 0, 0, ?)",
                      (user_id, username, datetime.now().isoformat()))
            conn.commit()
            coins, username, total_taps, referrals = 0, username, 0, 0
        else:
            coins, stored_username, total_taps, referrals = user
            username = stored_username or username
    
    c.execute("SELECT username, coins FROM users ORDER BY coins DESC LIMIT 5")
    leaderboard = c.fetchall()

    game_data = None
    if room_id:
        c.execute("SELECT * FROM games WHERE room_id = ? AND status = 'active'", (room_id,))
        game = c.fetchone()
        if game:
            game_data = {
                'room_id': game[0],
                'player1_id': game[1],
                'player2_id': game[2],
                'player1_score': game[3],
                'player2_score': game[4],
                'board': game[5],
                'current_turn': game[6],
                'mode': game[7],
                'duration': game[9]
            }

    return render_template('index.html', coins=coins, user_id=user_id, username=username,
                           total_taps=total_taps, referrals=referrals, leaderboard=leaderboard,
                           room_id=room_id, game_data=game_data)

@app.route('/make_move', methods=['POST'])
def make_move():
    user_id = request.args.get('user_id')
    room_id = request.args.get('room_id')
    row = int(request.args.get('row'))
    col = int(request.args.get('col'))
    
    if not user_id or not room_id:
        return jsonify({"error": "Missing user_id or room_id"}), 400
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        c.execute("SELECT player1_id, player2_id, board, current_turn, player1_score, player2_score FROM games WHERE room_id = ? AND status = 'active'", (room_id,))
        game = c.fetchone()
        if not game:
            return jsonify({"error": "Game not found"}), 404
        
        player1_id, player2_id, board, current_turn, player1_score, player2_score = game
        if user_id != current_turn:
            return jsonify({"error": "Not your turn"}), 400
        
        # Parse the board (stored as a JSON string)
        import json
        board = json.loads(board)
        
        # Chain Reaction logic
        player = 1 if user_id == player1_id else 2
        board, game_over, winner = process_chain_reaction(board, row, col, player)
        
        # Update scores
        player1_score = sum(1 for row in board for cell in row if cell > 0 and cell % 10 == 1)
        player2_score = sum(1 for row in board for cell in row if cell > 0 and cell % 10 == 2)
        
        # Switch turns
        next_turn = player2_id if user_id == player1_id else player1_id
        
        # Update game state
        status = 'active' if not game_over else 'finished'
        c.execute("UPDATE games SET board = ?, current_turn = ?, player1_score = ?, player2_score = ?, status = ? WHERE room_id = ?",
                  (json.dumps(board), next_turn, player1_score, player2_score, status, room_id))
        conn.commit()
        
        # Emit game update
        socketio.emit('game_update', {
            'room_id': room_id,
            'board': board,
            'current_turn': next_turn,
            'player1_score': player1_score,
            'player2_score': player2_score,
            'game_over': game_over,
            'winner': winner
        }, room=room_id)
    
    return jsonify({"board": board, "current_turn": next_turn, "player1_score": player1_score, "player2_score": player2_score})

@app.route('/create_game', methods=['POST'])
def create_game():
    user_id = request.args.get('user_id')
    username = request.args.get('username')
    mode = request.args.get('mode', 'rapid')
    duration = 60 if mode == 'rapid' else 30
    
    room_id = str(uuid.uuid4())
    # Initialize a 6x9 Chain Reaction board (0 = empty, 1x = player 1, 2x = player 2)
    board = [[0 for _ in range(9)] for _ in range(6)]
    
    with sqlite3.connect('users.db') as conn:
        c = conn.cursor()
        import json
        c.execute("INSERT INTO games (room_id, player1_id, board, current_turn, mode, start_time, duration, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting')",
                  (room_id, user_id, json.dumps(board), user_id, mode, datetime.now().isoformat(), duration))
        conn.commit()
    
    game_rooms[room_id] = {'player1_id': user_id, 'player2_id': None, 'mode': mode, 'duration': duration}
    return jsonify({"room_id": room_id})

@app.route('/debug', methods=['GET'])
def debug():
    return "Chain Reaction Game v1.0 - Flask is running!"

# Chain Reaction Logic
def process_chain_reaction(board, row, col, player):
    rows, cols = len(board), len(board[0])
    # Add atom to the cell
    board[row][col] = board[row][col] + (10 * player) + 1
    
    # Check critical mass (corner: 2, edge: 3, middle: 4)
    def get_critical_mass(r, c):
        if (r == 0 or r == rows - 1) and (c == 0 or c == cols - 1):
            return 2  # Corner
        elif r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
            return 3  # Edge
        return 4  # Middle
    
    # Chain reaction
    def explode(r, c):
        critical_mass = get_critical_mass(r, c)
        atoms = board[r][c] % 10
        if atoms < critical_mass:
            return
        
        # Reset cell and distribute atoms
        board[r][c] = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                board[nr][nc] = (board[nr][nc] % 10) + (10 * player) + 1
                explode(nr, nc)
    
    explode(row, col)
    
    # Check game over
    player1_cells = sum(1 for r in range(rows) for c in range(cols) if board[r][c] > 0 and board[r][c] % 10 == 1)
    player2_cells = sum(1 for r in range(rows) for c in range(cols) if board[r][c] > 0 and board[r][c] % 10 == 2)
    game_over = False
    winner = None
    if player1_cells == 0 and player2_cells > 0:
        game_over = True
        winner = 2
    elif player2_cells == 0 and player1_cells > 0:
        game_over = True
        winner = 1
    
    return board, game_over, winner

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
    if remainin
