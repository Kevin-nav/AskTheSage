# src/services/system_service.py
import logging
from typing import List
from telegram import Bot
from telegram.error import Forbidden, TelegramError
from sqlalchemy.orm import Session, joinedload

from src.database import get_db
from src.models.models import QuizSession

logger = logging.getLogger(__name__)

async def clear_all_active_sessions_for_update(bot: Bot):
    """
    Finds all 'in_progress' quiz sessions, notifies the users that the session
    was cancelled due to an update, and marks the sessions as 'incomplete'.
    """
    db: Session
    with get_db() as db:
        try:
            active_sessions: List[QuizSession] = (
                db.query(QuizSession)
                .options(joinedload(QuizSession.user))
                .filter(QuizSession.status == 'in_progress')
                .all()
            )

            if not active_sessions:
                logger.info("No active quiz sessions found to clear.")
                return

            logger.info(f"Found {len(active_sessions)} active sessions to clear for update.")
            
            notification_message = (
                "The bot is restarting for an update. Your current quiz session has been cancelled. "
                "Sorry for the inconvenience! You can start a new quiz shortly."
            )

            for session in active_sessions:
                session.status = 'incomplete'
                try:
                    # The user relationship is eager-loaded via joinedload
                    if session.user and session.user.telegram_id:
                        await bot.send_message(chat_id=session.user.telegram_id, text=notification_message)
                        logger.info(f"Notified user {session.user.telegram_id} about session cancellation.")
                except Forbidden:
                    logger.warning(f"Could not notify user {session.user.telegram_id}: Bot blocked.")
                except TelegramError as e:
                    logger.error(f"Error notifying user {session.user.telegram_id}: {e}")

            db.commit()
            logger.info("All active sessions have been marked as 'incomplete'.")

        except Exception as e:
            logger.error(f"An error occurred while clearing active sessions: {e}", exc_info=True)
            db.rollback()
