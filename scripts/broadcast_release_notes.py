import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from telegram import Bot
from telegram.error import TelegramError

from src.config import TELEGRAM_BOT_TOKEN
from src.services.broadcast_service import get_all_user_ids, broadcast_to_users
from src.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

RELEASE_NOTES_PATH = project_root / "docs" / "release_notes.md"

async def send_notifications():
    """Reads release notes and broadcasts them to all users."""
    logger.info("--- Update Notification Process Starting ---")
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Aborting.")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    logger.info(f"Reading release notes from {RELEASE_NOTES_PATH}")
    try:
        with open(RELEASE_NOTES_PATH, 'r', encoding='utf-8') as f:
            message = f.read()
        if not message.strip():
            raise ValueError("Release notes file is empty.")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Could not read release notes, aborting broadcast. Error: {e}")
        logger.info("--- Update Notification Process Failed ---")
        return

    logger.info("Fetching all user IDs for broadcast...")
    try:
        user_ids = get_all_user_ids()
        if user_ids:
            logger.info(f"Found {len(user_ids)} users to notify.")
            await broadcast_to_users(bot, user_ids, message)
        else:
            logger.info("No users found to broadcast to.")
    except Exception as e:
        logger.error(f"An error occurred while fetching user IDs or broadcasting. Error: {e}")
        logger.info("--- Update Notification Process Failed ---")
        return

    logger.info("--- Update Notification Process Complete ---")

if __name__ == "__main__":
    asyncio.run(send_notifications())
