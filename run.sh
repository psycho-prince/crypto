#!/bin/bash
python3 bot.py &  # Run bot in background
python3 webapp.py  # Run webapp in foreground (uses port 5000)