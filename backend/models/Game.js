const mongoose = require('mongoose');

const gameSchema = new mongoose.Schema({
  roomId: { type: String, required: true, unique: true },
  players: [{ type: String }],
  usernames: [{ type: String }],
  board: [[Number]],
  currentTurn: { type: String },
  status: { type: String, default: 'not_started' },
  winner: { type: Number },
  createdAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Game', gameSchema);
