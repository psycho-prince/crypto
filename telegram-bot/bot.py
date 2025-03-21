import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, InlineQueryHandler, ChosenInlineResultHandler, ContextTypes, ApplicationBuilder
from telegram.error import TelegramError
from dotenv import load_dotenv
import requests
import asyncio
from aiohttp import web

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
BACKEND_URL = os.getenv("BACKEND_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")
PORT = int(os.getenv("PORT", 8443))  # Default to 8443 if PORT is not set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize the bot
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name

    keyboard = [
        [InlineKeyboardButton("Play Chain Reaction", switch_inline_query_current_chat="")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Welcome, {username}! 🎮\nStart a Chain Reaction game!",
        reply_markup=reply_markup
    )
    logger.info(f"User {user_id} ({username}) started bot")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name

    help_text = (
        "🎮 *Chain Reaction Bot Help*\n\n"
        "Commands:\n"
        "/start - Start a new game\n"
        "/help - Show this help message\n\n"
        "How to Play:\n"
        "- Use /start to begin.\n"
        "- Click 'Play Chain Reaction' to create a game.\n"
        "- Share the link with friends to join (2-8 players).\n"
        "- Take turns placing atoms on the 6x9 grid.\n"
        "- Cause chain reactions to capture the board!\n"
        "- The last player standing wins."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")
    logger.info(f"User {user_id} ({username}) requested help")

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.inline_query.from_user
    user_id = str(user.id)
    username = user.username or user.first_name

    results = [
        {
            "type": "article",
            "id": "create_game",
            "title": "Start a Chain Reaction Game",
            "description": "Play a 6x9 Chain Reaction game with friends!",
            "input_message_content": {
                "message_text": f"{username} is creating a Chain Reaction game...",
                "parse_mode": "Markdown"
            },
            "reply_markup": {
                "inline_keyboard": [[{"text": "Waiting...", "callback_data": "creating-room"}]]
            }
        }
    ]

    await update.inline_query.answer(results, cache_time=0)
    logger.info(f"User {user_id} ({username}) initiated inline query")

async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chosen_inline_result.from_user
    user_id = str(user.id)
    username = user.username or user.first_name
    result_id = update.chosen_inline_result.result_id
    inline_message_id = update.chosen_inline_result.inline_message_id

    if result_id == "create_game":
        try:
            response = requests.post(
                f"{BACKEND_URL}/create_game",
                json={"userId": user_id, "username": username},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            room_id = data["roomId"]
        except requests.RequestException as e:
            logger.error(f"Failed to create game for user {user_id}: {e}")
            await context.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text="Failed to create game. Please try again.",
                reply_markup=InlineKeyboardMarkup([])
            )
            return

        game_url = f"{FRONTEND_URL}/?user_id={user_id}&username={username}&room_id={room_id}"
        message_text = f"{username} started a Chain Reaction game! Join now!"
        keyboard = [[InlineKeyboardButton("Join", web_app=WebAppInfo(url=game_url))]]
        await context.bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Game {room_id} created for user {user_id} ({username})")

# Add handlers
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(InlineQueryHandler(inline_query))
bot_app.add_handler(ChosenInlineResultHandler(chosen_inline_result))

# Webhook handler for Render
async def webhook(request):
    update = await request.json()
    update = Update.de_json(update, bot_app.bot)
    await bot_app.process_update(update)
    return web.Response(text="OK")

async def set_webhook():
    try:
        await bot_app.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
    except TelegramError as e:
        logger.error(f"Failed to set webhook: {e}")

if __name__ == "__main__":
    if os.getenv("RENDER"):
        # Run in webhook mode on Render
        app = web.Application()
        app.router.add_post('/webhook', webhook)
        
        # Initialize the bot and set the webhook
        loop = asyncio.get_event_loop()
        loop.run_until_complete(bot_app.initialize())
        loop.run_until_complete(set_webhook())
        
        # Start the web server
        logger.info(f"Starting webhook server on port {PORT}")
        web.run_app(app, port=PORT)
    else:
        # Run in polling mode locally
        bot_app.run_polling()
