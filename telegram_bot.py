import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from dotenv import load_dotenv

# Load .env file (for local use; Replit uses Secrets)
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect("users.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, wallet TEXT, crypto TEXT, pool TEXT)")
conn.commit()

# Keep-alive server for Replit
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_server():
    server = HTTPServer(("", 8080), KeepAlive)
    server.serve_forever()

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use /register <crypto> <wallet> to set up mining.")
    logger.info(f"User {update.effective_user.id} started the bot")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /register <crypto> <wallet>")
        return
    crypto, wallet = args
    c.execute("INSERT OR REPLACE INTO users (user_id, wallet, crypto, pool) VALUES (?, ?, ?, 'default_pool')",
              (user_id, wallet, crypto))
    conn.commit()
    await update.message.reply_text(f"Registered {crypto} wallet: {wallet}")
    logger.info(f"User {user_id} registered {crypto} wallet: {wallet}")

async def mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT wallet, crypto, pool FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        await update.message.reply_text("Please /register first!")
        return
    wallet, crypto, pool = user_data
    context.user_data["mining"] = True
    await update.message.reply_text(f"Started mining {crypto} to {wallet} on {pool} (simulated).")
    logger.info(f"User {user_id} started mining {crypto}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mining = context.user_data.get("mining", False)
    c.execute("SELECT wallet, crypto FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    if not user_data:
        await update.message.reply_text("Not registered yet!")
        return
    wallet, crypto = user_data
    status = "Mining" if mining else "Not mining"
    await update.message.reply_text(f"Status: {status}\nCrypto: {crypto}\nWallet: {wallet}")
    logger.info(f"User {user_id} checked status: {status}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get("mining", False):
        context.user_data["mining"] = False
        await update.message.reply_text("Mining stopped.")
        logger.info(f"User {user_id} stopped mining")
    else:
        await update.message.reply_text("Not mining!")

async def profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mining = context.user_data.get("mining", False)
    if mining:
        await update.message.reply_text("Profit: 0.0001 XMR (simulated)")
    else:
        await update.message.reply_text("Not mining, no profit!")
    logger.info(f"User {user_id} checked profit")

# Main function
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN not set!")
        raise ValueError("Set TELEGRAM_TOKEN in .env or Replit Secrets")
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("mine", mine))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("profit", profit))
    logger.info("Starting bot polling...")
    threading.Thread(target=run_server, daemon=True).start()
    application.run_polling()

if __name__ == "__main__":
    main()
