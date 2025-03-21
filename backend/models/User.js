const mongoose = require('mongoose');

const userSchema = new mongoose.Schema({
  userId: { type: String, required: true, unique: true },
  username: { type: String, required: true },
  wins: { type: Number, default: 0 },
  lastRoomId: { type: String }
});

module.exports = mongoose.model('User', userSchema);
