# src/services/broadcast_service.py
import asyncio
import logging
from typing import List
from telegram import Bot
from telegram.error import Forbidden, TelegramError

from src.database import get_db
from src.models.models import User

logger = logging.getLogger(__name__)

def get_all_user_ids() -> List[int]:
    """
    Retrieves a list of all user Telegram IDs from the database.
    """
    with get_db() as session:
        user_ids = session.query(User.telegram_id).all()
        return [uid[0] for uid in user_ids]

async def send_broadcast_message(
    bot: Bot, 
    user_id: int, 
    message: str, 
    photo_path: str = None, 
    document_path: str = None
) -> bool:
    """
    Sends a single message to a user, with an optional photo or document.
    Returns True on success, False on failure.
    """
    try:
        if photo_path:
            with open(photo_path, 'rb') as photo_file:
                await bot.send_photo(chat_id=user_id, photo=photo_file, caption=message, parse_mode="Markdown")
        elif document_path:
            with open(document_path, 'rb') as doc_file:
                await bot.send_document(chat_id=user_id, document=doc_file, caption=message, parse_mode="Markdown")
        elif message: # Only send if there is a message
            await bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
        else:
            # This case should ideally be handled by the calling script
            logger.warning(f"No message, photo, or document to send to user {user_id}. Skipping.")
            return False
        return True
    except Forbidden:
        logger.warning(f"Failed to send message to user {user_id}: Bot was blocked or user deactivated account.")
    except TelegramError as e:
        logger.error(f"Failed to send message to user {user_id}: {e}")
    return False

async def broadcast_to_users(
    bot: Bot, 
    user_ids: List[int], 
    message: str, 
    photo_path: str = None, 
    document_path: str = None
):
    """
    Broadcasts a message to a list of users with progress and error handling.
    """
    total_users = len(user_ids)
    success_count = 0
    failure_count = 0

    logger.info(f"Starting broadcast to {total_users} users...")

    for i, user_id in enumerate(user_ids):
        if await send_broadcast_message(bot, user_id, message, photo_path, document_path):
            success_count += 1
        else:
            failure_count += 1
        
        if (i + 1) % 25 == 0:
            logger.info(f"Progress: {i + 1}/{total_users} users processed.")
        
        await asyncio.sleep(0.04)  # 40ms delay to stay under Telegram's 30 msg/sec limit

    logger.info("-" * 20)
    logger.info("Broadcast finished.")
    logger.info(f"Summary: {success_count} successful, {failure_count} failed.")
    logger.info("-" * 20)
