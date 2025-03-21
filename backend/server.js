const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const mongoose = require('mongoose');
const dotenv = require('dotenv');
const cors = require('cors');
const apiRoutes = require('./routes/api');
const User = require('./models/User');
const Game = require('./models/Game');

dotenv.config();

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: process.env.FRONTEND_URL,
    methods: ['GET', 'POST']
  }
});

app.use(cors());
app.use(express.json());
app.use('/api', apiRoutes);

mongoose.connect(process.env.MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('Connected to MongoDB'))
  .catch(err => console.error('MongoDB connection error:', err));

class ChainReactionGame {
  constructor(roomId, hostId, hostUsername) {
    this.roomId = roomId;
    this.players = [hostId];
    this.usernames = [hostUsername];
    this.board = Array(6).fill().map(() => Array(9).fill(0));
    this.currentTurn = hostId;
    this.status = 'not_started';
    this.winner = null;
    this.maxPlayers = 8;
  }

  addPlayer(playerId, username) {
    if (this.players.length >= this.maxPlayers || this.players.includes(playerId)) {
      return false;
    }
    this.players.push(playerId);
    this.usernames.push(username);
    if (this.players.length >= 2 && this.status === 'not_started') {
      this.status = 'in_progress';
    }
    return true;
  }

  makeMove(playerId, row, col) {
    if (this.status !== 'in_progress' || playerId !== this.currentTurn) {
      return { success: false, reactions: [] };
    }

    const player = this.players.indexOf(playerId) + 1;
    if (row < 0 || row >= 6 || col < 0 || col >= 9) {
      return { success: false, reactions: [] };
    }

    this.board[row][col] = (this.board[row][col] % 10) + (10 * player) + 1;
    const reactions = this.processChainReaction(row, col, player);

    const scores = this.players.map((_, p) =>
      this.board.flat().filter(cell => cell > 0 && Math.floor(cell / 10) === (p + 1)).length
    );

    const activePlayers = scores.filter(score => score > 0).length;
    if (activePlayers <= 1 && this.players.length > 1) {
      this.status = 'finished';
      const winnerIdx = scores.findIndex(score => score > 0);
      if (winnerIdx !== -1) {
        this.winner = winnerIdx + 1;
        this.updateWins(this.players[winnerIdx]);
      }
    }

    if (this.status === 'in_progress') {
      const currentIdx = this.players.indexOf(playerId);
      this.currentTurn = this.players[(currentIdx + 1) % this.players.length];
    }

    return { success: true, reactions };
  }

  async updateWins(winnerId) {
    await User.findOneAndUpdate({ userId: winnerId }, { $inc: { wins: 1 } });
  }

  processChainReaction(row, col, player) {
    const reactions = [];
    const rows = 6, cols = 9;
    let criticalMass = 4;
    if ((row === 0 || row === rows - 1) && (col === 0 || col === cols - 1)) {
      criticalMass = 2;
    } else if (row === 0 || row === rows - 1 || col === 0 || col === cols - 1) {
      criticalMass = 3;
    }

    const atoms = this.board[row][col] % 10;
    if (atoms < criticalMass) {
      return reactions;
    }

    reactions.push({ row, col, player });
    this.board[row][col] = 0;
    const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];
    for (const [dr, dc] of directions) {
      const nr = row + dr, nc = col + dc;
      if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
        this.board[nr][nc] = (this.board[nr][nc] % 10) + (10 * player) + 1;
        const subReactions = this.processChainReaction(nr, nc, player);
        reactions.push(...subReactions);
      }
    }
    return reactions;
  }

  toJSON() {
    return {
      roomId: this.roomId,
      players: this.players,
      usernames: this.usernames,
      board: this.board,
      currentTurn: this.currentTurn,
      status: this.status,
      winner: this.winner
    };
  }
}

const games = new Map();

io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);

  socket.on('create_game', async ({ userId, username }) => {
    const roomId = require('crypto').randomUUID();
    const game = new ChainReactionGame(roomId, userId, username);
    games.set(roomId, game);

    await User.findOneAndUpdate(
      { userId },
      { userId, username, lastRoomId: roomId },
      { upsert: true }
    );

    await new Game({
      roomId,
      players: [userId],
      usernames: [username],
      board: game.board,
      currentTurn: userId,
      status: 'not_started'
    }).save();

    socket.join(roomId);
    socket.emit('game_created', { roomId, gameData: game.toJSON() });
  });

  socket.on('join_game', async ({ roomId, userId, username }) => {
    let game = games.get(roomId);
    if (!game) {
      const gameDoc = await Game.findOne({ roomId });
      if (gameDoc) {
        game = new ChainReactionGame(roomId, gameDoc.players[0], gameDoc.usernames[0]);
        game.players = gameDoc.players;
        game.usernames = gameDoc.usernames;
        game.board = gameDoc.board;
        game.currentTurn = gameDoc.currentTurn;
        game.status = gameDoc.status;
        game.winner = gameDoc.winner;
        games.set(roomId, game);
      } else {
        socket.emit('join_error', { error: 'Game not found' });
        return;
      }
    }

    if (game.addPlayer(userId, username)) {
      await Game.findOneAndUpdate(
        { roomId },
        { players: game.players, usernames: game.usernames, status: game.status }
      );
      await User.findOneAndUpdate(
        { userId },
        { userId, username, lastRoomId: roomId },
        { upsert: true }
      );

      socket.join(roomId);
      io.to(roomId).emit('game_start', game.toJSON());
      io.to(roomId).emit('player_joined', { username });
    } else {
      socket.emit('join_error', { error: 'Unable to join game' });
    }
  });

  socket.on('make_move', async ({ roomId, userId, row, col }) => {
    const game = games.get(roomId);
    if (!game) {
      socket.emit('error', { error: 'Game not found' });
      return;
    }

    const { success, reactions } = game.makeMove(userId, row, col);
    if (success) {
      await Game.findOneAndUpdate(
        { roomId },
        { board: game.board, currentTurn: game.currentTurn, status: game.status, winner: game.winner }
      );
      io.to(roomId).emit('game_update', game.toJSON());
      if (reactions.length > 0) {
        io.to(roomId).emit('chain_reaction', reactions);
      }
    } else {
      socket.emit('error', { error: 'Invalid move' });
    }
  });

  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
