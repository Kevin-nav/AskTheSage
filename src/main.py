import asyncio
import logging
import argparse
import sys
import os
from telegram import Update, BotCommand, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, PicklePersistence

from src.config import TELEGRAM_BOT_TOKEN
from src.handlers.conversation_handlers import quiz_conv_handler
from src.handlers.general_handlers import start, help_command, performance_command
from src.handlers.feedback_handler import get_feedback_conversation_handler
from src.handlers.admin_handlers import get_admin_feedback_handler, get_admin_question_handlers
from src.logging_config import setup_logging
from src.services.broadcast_service import get_all_user_ids, broadcast_to_users
from src.services.system_service import clear_all_active_sessions_for_update

# --- Argument Parsing ---
# We parse arguments here at the module level so they can be accessed in post_init
parser = argparse.ArgumentParser(description="Sir Johnson Study Bot")
parser.add_argument(
    '--notify-update',
    action='store_true',
    help='On startup, cancel active quizzes, send docs/release_notes.md to all users, then run normally.'
)
ARGS = parser.parse_args()

# --- Bot Setup ---
setup_logging()
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)

async def set_bot_commands(application: Application):
    """Sets the bot's commands available in the Telegram menu."""
    await application.bot.set_my_commands([
        BotCommand("quiz", "Start a new quiz session"),
        BotCommand("help", "Show help information"),
        BotCommand("performance", "See your quiz performance"),
        BotCommand("feedback", "Provide feedback or report an issue"),
        BotCommand("cancel", "Cancel the current operation or quiz")
    ])

async def post_init_hook(application: Application):
    """Post-initialization function. Sets commands and runs update notification if requested."""
    # First, set the bot commands
    await set_bot_commands(application)

    # Then, check if the --notify-update flag was used
    if ARGS.notify_update:
        logger.info("--- UPDATE NOTIFICATION PROCESS STARTING ---")
        bot = application.bot

        # 1. Clear active sessions and notify affected users
        await clear_all_active_sessions_for_update(bot)

        # 2. Broadcast release notes to all users
        release_notes_path = "docs/release_notes.md"
        logger.info(f"Reading release notes from {release_notes_path}")
        try:
            with open(release_notes_path, 'r', encoding='utf-8') as f:
                message = f.read()
            if not message.strip():
                raise ValueError("Release notes file is empty.")
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Could not read release notes, aborting broadcast. Error: {e}")
            logger.info("--- UPDATE NOTIFICATION PROCESS FAILED ---")
            return

        logger.info("Fetching all user IDs for broadcast...")
        user_ids = get_all_user_ids()
        if user_ids:
            await broadcast_to_users(bot, user_ids, message)
        else:
            logger.info("No users found to broadcast to.")
        
        logger.info("--- UPDATE NOTIFICATION PROCESS COMPLETE ---")

def main() -> None:
    """Run the bot."""
    logger.info("Bot is starting...")

    # Create the Application and pass it your bot's token.
    persistence = PicklePersistence(filepath="persistence.pickle")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).persistence(persistence).post_init(post_init_hook).build()

    # Add conversation handler with the states
    application.add_handler(quiz_conv_handler)
    application.add_handler(get_feedback_conversation_handler())

    # Add other command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("performance", performance_command))

    # Add admin handlers
    application.add_handler(get_admin_feedback_handler())
    admin_question_handlers = get_admin_question_handlers()
    for handler in admin_question_handlers:
        application.add_handler(handler)

    # Register the error handler
    application.add_error_handler(error_handler)

    logger.info("Bot is running... Send /quiz to start.")
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
