import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import TELEGRAM_BOT_TOKEN, WELCOME_MESSAGE
from src.handlers.conversation_handlers import quiz_conv_handler
from src.handlers.general_handlers import start, help_command, performance_command
from src.logging_config import setup_logging

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger = logging.getLogger(__name__)
    logger.error("Exception while handling an update:", exc_info=context.error)

async def post_init(application: Application):
    """Post-initialization function to set bot commands."""
    await application.bot.set_my_commands([
        BotCommand("quiz", "Start a new quiz session"),
        BotCommand("help", "Show help information"),
        BotCommand("performance", "See your quiz performance"),
        BotCommand("cancel", "Cancel the current operation or quiz")
    ])

def main() -> None:
    """Run the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Bot is starting...")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Add conversation handler with the states
    application.add_handler(quiz_conv_handler)

    # Add other command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("performance", performance_command))

    # Register the error handler
    application.add_error_handler(error_handler)

    logger.info("Bot is running... Send /quiz to start.")
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
