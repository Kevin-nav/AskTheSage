# src/handlers/admin_handlers.py

import logging
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
)
from sqlalchemy.orm import joinedload

from src.models.models import User, Feedback, Question
from src.database import get_db
from src.services.notification_service import (
    update_feedback_notification,
    notify_user_of_status_change,
)

logger = logging.getLogger(__name__)

async def handle_feedback_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles admin actions on feedback items."""
    query = update.callback_query
    logger.info(f"Admin action '{query.data}' received from user {update.effective_user.id}")
    await query.answer()
    logger.info("Callback query answered.")

    admin_user = update.effective_user

    # Security Check: Ensure the user is an admin
    logger.info("Checking admin status...")
    with get_db() as session:
        db_admin_user = session.query(User).filter(User.telegram_id == admin_user.id, User.is_admin == True).first()
        if not db_admin_user:
            logger.warning(f"Non-admin user {admin_user.id} attempted action: {query.data}")
            await query.answer("This action is for admins only.", show_alert=True)
            return
    logger.info("Admin status confirmed.")

    # Parse action and feedback_id from callback_data
    try:
        _, _, action, feedback_id_str = query.data.split("_")
        feedback_id = int(feedback_id_str)
        logger.info(f"Parsed action: '{action}', feedback_id: {feedback_id}")
    except ValueError:
        logger.error(f"Could not parse callback_data: {query.data}")
        return

    logger.info("Entering main logic block...")
    with get_db() as session:
        logger.info("Fetching feedback item from DB...")
        # Eagerly load the user relationship to ensure access for the DM notification
        feedback = session.query(Feedback).options(joinedload(Feedback.user)).filter(Feedback.id == feedback_id).first()

        if not feedback:
            logger.warning(f"Feedback item {feedback_id} not found in DB.")
            await query.answer("This feedback item could not be found.", show_alert=True)
            return

        logger.info(f"Feedback item {feedback_id} found with status '{feedback.status}'.")

        # State machine logic
        original_status = feedback.status
        if action == "ack" and feedback.status == 'open':
            feedback.status = 'in_progress'
        elif action == "resolve" and feedback.status == 'in_progress':
            feedback.status = 'resolved'
        elif action == "dismiss" and feedback.status == 'open':
            feedback.status = 'dismissed'
        else:
            # This can happen in a race condition, e.g., two admins clicking at once
            logger.warning(f"Invalid state transition attempted for feedback {feedback_id}. Action: '{action}', Status: '{feedback.status}'")
            await query.answer(f"This item is no longer in the '{original_status}' state.", show_alert=True)
            return
        
        logger.info(f"Attempting to commit status change for feedback {feedback_id} from '{original_status}' to '{feedback.status}'...")
        session.commit()
        logger.info("Commit successful.")

        # Update the original message in the admin group
        logger.info("Attempting to update feedback notification message...")
        await update_feedback_notification(context.bot, query, feedback, admin_user.username)
        logger.info("Successfully updated feedback notification message.")

        # Notify the user via DM
        logger.info(f"Attempting to notify user {feedback.user.id} of status change...")
        await notify_user_of_status_change(context.bot, feedback)
        logger.info("Successfully notified user.")


def get_admin_feedback_handler() -> CallbackQueryHandler:
    """Creates the handler for admin feedback actions."""
    return CallbackQueryHandler(handle_feedback_action, pattern="^feedback_admin_")

async def view_question_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'View Question Details' button press from an admin."""
    query = update.callback_query
    await query.answer()

    question_id = int(query.data.split('_')[3])

    with get_db() as db:
        question = db.query(Question).filter(Question.id == question_id).first()

        if not question:
            await query.edit_message_text("Sorry, I couldn't find that question.")
            return

        # Format the details message
        details_text = (
            f"**Question Details (ID: {question.id})**\n\n"
            f"**Course:** {question.course.name}\n"
            f"**Difficulty:** {question.difficulty_score}\n\n"
            f"**Correct Answer:** {question.correct_answer}"
        )

        # Send the main question content (image or text)
        if question.image_url:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=question.image_url,
                caption=f"**Question ID: {question.id}**",
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"**Question ID: {question.id}**\n\n{question.question_text}",
                parse_mode="Markdown"
            )
        
        # Send the options
        options_text = "\n".join([f"- {opt}" for opt in question.options.values()])
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"**Options:**\n{options_text}",
            parse_mode="Markdown"
        )

        # Send the explanation (image or text)
        if question.explanation_image_url:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=question.explanation_image_url,
                caption="**Explanation**",
                parse_mode="Markdown"
            )
        elif question.explanation:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"**Explanation:**\n{question.explanation}",
                parse_mode="Markdown"
            )
        
        # Send the other details
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=details_text,
            parse_mode="Markdown"
        )

def get_admin_question_handlers():
    return [
        CallbackQueryHandler(view_question_details, pattern="^admin_view_question_"),
    ]