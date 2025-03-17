import sqlite3
import logging
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from miner import Miner

# Bot token from @BotFather
TOKEN = "7995392986:AAGYT8QpFz160rWs5J0IHfozylMzgrGHBlE"

# Supported cryptocurrencies and their pools
POOLS = {
    "ethereum": "stratum+tcp://us1.ethermine.org:4444",
    "bitcoin": "stratum+tcp://pool.bitcoin.com:3333",
    "monero": "stratum+tcp://pool.supportxmr.com:3333",
    "litecoin": "stratum+tcp://litecoinpool.org:3333"
}

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, wallet TEXT, crypto TEXT, pool TEXT)")
conn.commit()

# Store active miners
miners = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    logger.info(f"User {user.id} started bot")
    await update.message.reply_text(
        f"Welcome, {user.first_name}! This is your Crypto Mining Bot.\n\n"
        "Commands:\n"
        "/register <crypto> <wallet> - Set your mining details\n"
        "/mine - Start mining\n"
        "/stop - Stop mining\n"
        "/status - Check mining status\n"
        "/profit - See current profitability\n\n"
        f"Supported cryptos: {', '.join(POOLS.keys())}"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /register <crypto> <wallet>\n"
            "Example: /register monero 4AYourMoneroWallet"
        )
        return

    crypto = args[0].lower()
    wallet = " ".join(args[1:])
    if crypto not in POOLS:
        await update.message.reply_text(f"Unsupported crypto. Choose from: {', '.join(POOLS.keys())}")
        return

    c.execute("INSERT OR REPLACE INTO users (user_id, wallet, crypto, pool) VALUES (?, ?, ?, ?)",
              (user_id, wallet, crypto, POOLS[crypto]))
    conn.commit()
    logger.info(f"User {user_id} registered: {crypto} -> {wallet}")
    await update.message.reply_text(f"Registered! Mining {crypto} to {wallet}")

async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in miners:
        await update.message.reply_text("You're already mining!")
        return

    c.execute("SELECT wallet, crypto, pool FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if not result:
        await update.message.reply_text("Please use /register first!")
        return

    wallet, crypto, pool = result
    miner = Miner(pool=pool, wallet=wallet, crypto=crypto, threads=1)
    miners[user_id] = miner
    miner.run_in_thread()
    logger.info(f"User {user_id} started mining {crypto}")
    await update.message.reply_text(f"Started mining {crypto}! Check your pool for stats.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in miners:
        await update.message.reply_text("You're not mining!")
        return

    miners[user_id].stop_mining()
    del miners[user_id]
    logger.info(f"User {user_id} stopped mining")
    await update.message.reply_text("Mining stopped.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in miners:
        await update.message.reply_text("You're not mining!")
        return
    await update.message.reply_text("Mining is active. Check your pool dashboard for details.")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    c.execute("SELECT crypto FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if not result:
        await update.message.reply_text("Please use /register first!")
        return

    crypto = result[0]
    miner = Miner(pool="", wallet="", crypto=crypto)  # Dummy miner for profitability
    profitability = miner.get_profitability()
    await update.message.reply_text(f"24h Profitability for {crypto}: {profitability}%")

def main():
    try:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("register", register))
        app.add_handler(CommandHandler("mine", mine))
        app.add_handler(CommandHandler("stop", stop))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("profit", profit))
        logger.info("Starting bot polling...")
        app.run_polling()
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")

if __name__ == "__main__":
    main()
