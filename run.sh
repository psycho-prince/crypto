#!/bin/bash
python3 bot.py &    # Telegram bot in background
python3 webapp.py   # Flask webapp in foreground (port 5000)