from telegram.ext import Application, CommandHandler
import minero  # Import minero locally
import threading
import sqlite3

# Your bot token from @BotFather
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# Store miners and user data
miners = {}
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, wallet TEXT, pool TEXT)")

# Supported pools
POOLS = {
    "ethereum": "stratum+tcp://us1.ethermine.org:4444",
    "bitcoin": "stratum+tcp://pool.bitcoin.com:3333",
    "monero": "stratum+tcp://pool.supportxmr.com:3333"
}

async def start(update, context):
    user = update.message.from_user
    await update.message.reply_text(
        f"Hello, {user.first_name}! I’m your Crypto Mining Bot.\n"
        "Steps:\n1. /register <crypto> <wallet> (e.g., /register ethereum 0xYourAddress)\n"
        "2. /mine - Start mining\n3. /stop - Stop mining\n4. /status - Check status\n"
        "Supported cryptos: {', '.join(POOLS.keys())}"
    )

async def register(update, context):
    user_id = update.message.from_user.id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /register <crypto> <wallet>\nExample: /register ethereum 0xYourAddress")
        return

    crypto, wallet = args[0].lower(), " ".join(args[1:])
    if crypto not in POOLS:
        await update.message.reply_text(f"Unsupported crypto. Available: {', '.join(POOLS.keys())}")
        return

    c.execute("INSERT OR REPLACE INTO users (user_id, wallet, pool) VALUES (?, ?, ?)",
              (user_id, wallet, POOLS[crypto]))
    conn.commit()
    await update.message.reply_text(f"Registered! Crypto: {crypto}, Wallet: {wallet}")

async def mine(update, context):
    user_id = update.message.from_user.id
    if user_id in miners:
        await update.message.reply_text("You're already mining!")
        return

    c.execute("SELECT wallet, pool FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if not result:
        await update.message.reply_text("Please /register your wallet and crypto first!")
        return

    wallet, pool = result
    miner = minero.Miner(pool=pool, wallet=wallet, password="x", threads=1)
    miners[user_id] = miner
    thread = threading.Thread(target=miner.start_mining)
    thread.daemon = True
    thread.start()
    await update.message.reply_text("Mining started! Check your pool for stats.")

async def stop(update, context):
    user_id = update.message.from_user.id
    if user_id not in miners:
        await update.message.reply_text("You're not mining!")
        return

    miners[user_id].stop_mining()
    del miners[user_id]
    await update.message.reply_text("Mining stopped.")

async def status(update, context):
    user_id = update.message.from_user.id
    if user_id not in miners:
        await update.message.reply_text("You're not mining!")
        return
    await update.message.reply_text("Mining is active. Check your pool dashboard for details.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("mine", mine))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.run_polling()

if __name__ == "__main__":
    main()
