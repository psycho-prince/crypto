import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, InlineQueryHandler, ChosenInlineResultHandler, ContextTypes
from telegram.error import TelegramError
from dotenv import load_dotenv
import requests
import asyncio

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
BACKEND_URL = os.getenv("BACKEND_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chosen_inline_result.from_user
    user_id = str(user.id)
    username = user.username or user.first_name
    result_id = update.chosen_inline_result.result_id
    inline_message_id = update.chosen_inline_result.inline_message_id

    if result_id == "create_game":
        try:
            response = requests.post(f"{BACKEND_URL}/create_game", json={"userId": user_id, "username": username})
            response.raise_for_status()
            data = response.json()
            room_id = data["roomId"]
        except Exception as e:
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

bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(InlineQueryHandler(inline_query))
bot_app.add_handler(ChosenInlineResultHandler(chosen_inline_result))

# Comment out webhook setup for local testing
# async def set_webhook():
#     await bot_app.bot.set_webhook(url=WEBHOOK_URL)
#     logger.info(f"Webhook set to {WEBHOOK_URL}")

if __name__ == "__main__":
    # Create a new event loop explicitly
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Run with polling instead of webhook for local testing
    bot_app.run_polling()
