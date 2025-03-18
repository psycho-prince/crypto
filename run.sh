
#!/bin/bash
python3 bot.py &    # Telegram bot in background
python3 web.py   # Flask webapp in foreground (port 5000)
