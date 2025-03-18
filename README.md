# Telegram Crypto Mining Bot

A Telegram bot for simulated cryptocurrency mining (with plans for genuine mining), hosted on Replit. Edit on GitHub and deploy for free.

## Features
- **Commands**:
  - `/start`: Welcome message.
  - `/help`: How to use the bot in Telegram.
  - `/register <crypto> <wallet>`: Register a wallet (e.g., `monero 4AYourWallet`).
  - `/mine`: Start simulated mining (real mining planned).
  - `/status`: Check mining status.
  - `/stop`: Stop mining.
  - `/profit`: View simulated profit (e.g., 0.0001 XMR).
- **Database**: SQLite (`users.db`).
- **Hosting**: Replit with keep-alive server.

## How to Use in Telegram
1. **Find the Bot**:
   - Open Telegram, search for `@YourBotName` (set via BotFather).
2. **Start It**:
   - Type `/start` to begin.
3. **Get Help**:
   - Use `/help` for full instructions.
4. **Register**:
   - Example: `/register monero 4AYourMoneroWallet`.
5. **Mine**:
   - Type `/mine` to start (simulated for now).
6. **Monitor**:
   - Use `/status` and `/profit` to track progress.
7. **Stop**:
   - Type `/stop` to pause mining.
