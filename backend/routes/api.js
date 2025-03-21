const express = require('express');
const router = express.Router();
const User = require('../models/User');
const Game = require('../models/Game');

router.get('/leaderboard', async (req, res) => {
  try {
    const leaders = await User.find().sort({ wins: -1 }).limit(10);
    res.json(leaders.map(user => ({ username: user.username, wins: user.wins })));
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch leaderboard' });
  }
});

module.exports = router;
