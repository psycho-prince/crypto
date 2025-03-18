# Telegram Crypto Mining Bot

A Telegram bot for simulated cryptocurrency mining, built with Python and hosted on Replit. Edit directly on GitHub and deploy on Replit for free.

## Features
- **Commands**:
  - `/start`: Welcome message.
  - `/register <crypto> <wallet>`: Register a crypto wallet.
  - `/mine`: Start simulated mining.
  - `/status`: Check mining status.
  - `/stop`: Stop mining.
  - `/profit`: View simulated profit (0.0001 XMR).
- **Database**: SQLite (`users.db`).
- **Hosting**: Replit with keep-alive server.

## Setup on GitHub
1. **Edit Files**:
   - Update files directly on `https://github.com/psycho-prince/crypto` (branch: `main`).
   - Replace with the above files if needed.

2. **Commit**:
   - Use GitHub’s web editor to commit changes.

## Deploy on Replit
1. **Sign Up**:
   - [replit.com](https://replit.com) > Sign in with GitHub (`psycho-prince`).

2. **Import Repo**:
   - New Repl > Python > Name: `telebot-miner`.
   - Sidebar > "Version Control" > "Import from GitHub" > `psycho-prince/crypto` > Branch: `main`.

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
