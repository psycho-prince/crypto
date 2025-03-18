# Telegram Crypto Mining Bot

A simple Telegram bot that simulates cryptocurrency mining, built with Python and deployed on Replit. Users can register a wallet, start/stop mining, check status, and view simulated profits.

## Features
- **Commands**:
  - `/start`: Welcome message.
  - `/register <crypto> <wallet>`: Register a cryptocurrency and wallet.
  - `/mine`: Start simulated mining.
  - `/status`: Check mining status and wallet.
  - `/stop`: Stop mining.
  - `/profit`: View simulated profit (e.g., 0.0001 XMR).
- **Database**: SQLite (`users.db`) stores user data.
- **Hosting**: Runs on Replit with a keep-alive HTTP server.

2. **Add Files**:
   - `telegram_bot.py`: Main bot code.
   - `requirements.txt`: Dependencies.
   - `.replit`: Run config.
   - `README.md`: This file.

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
