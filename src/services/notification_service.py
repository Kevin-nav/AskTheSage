# src/services/notification_service.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from telegram.error import Forbidden

from src.config import TELEGRAM_ADMIN_GROUP_ID
from src.models.models import Feedback

logger = logging.getLogger(__name__)


def get_admin_buttons(feedback: Feedback) -> InlineKeyboardMarkup:
    """Generates the appropriate inline keyboard for a feedback item."""
    keyboard = []
    if feedback.status == 'open':
        keyboard = [
            [InlineKeyboardButton("Acknowledge", callback_data=f"feedback_admin_ack_{feedback.id}")],
            [InlineKeyboardButton("Dismiss", callback_data=f"feedback_admin_dismiss_{feedback.id}")],
        ]
    elif feedback.status == 'in_progress':
        keyboard = [
            [InlineKeyboardButton("Mark as Resolved", callback_data=f"feedback_admin_resolve_{feedback.id}")]
        ]
    # No buttons for resolved or dismissed items
    return InlineKeyboardMarkup(keyboard)


async def send_new_feedback_notification(bot: Bot, feedback: Feedback, user_username: str):
    """Sends a notification to the admin group about new feedback."""
    if not TELEGRAM_ADMIN_GROUP_ID:
        logger.warning("TELEGRAM_ADMIN_GROUP_ID not set. Cannot send new feedback notification.")
        return

    if feedback.feedback_type == 'question_report' and feedback.question:
        question = feedback.question
        question_text = question.question_text
        if len(question_text) > 500:
            question_text = question_text[:500] + "..."
        
        options_text = "\n".join([f"- {opt}" for opt in question.options.values()])

        text = (
            f"**🚨 New Question Report: #{feedback.id}**\n\n"
            f"**From:** @{user_username}\n"
            f"**Course:** {question.course.name}\n"
            f"**Reason:** {feedback.text_content.replace('_', ' ').capitalize()}\n\n"
            f"**Question Text:**\n_{question_text}_\n\n"
            f"**Options:**\n{options_text}\n\n"
            f"**Correct Answer:** {question.correct_answer}"
        )
    else:
        text = (
            f"**New Feedback Submission: #{feedback.id}**\n\n"
            f"**From:** @{user_username}\n"
            f"**Type:** {feedback.feedback_type.capitalize()}\n"
            f"**Content:**\n{feedback.text_content}"
        )

    reply_markup = get_admin_buttons(feedback)

    logger.info(f"Attempting to send feedback notification to admin group ID: {TELEGRAM_ADMIN_GROUP_ID}")

    try:
        await bot.send_message(
            chat_id=TELEGRAM_ADMIN_GROUP_ID,
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send new feedback notification to admin group: {e}")


async def update_feedback_notification(bot: Bot, query: Update.callback_query, feedback: Feedback, admin_username: str):
    """Edits the original feedback notification after an admin action."""
    status_text = feedback.status.replace("_", " ").capitalize()
    text = (
        f"**Feedback #{feedback.id} (Status: {status_text})**\n\n"
        f"**From:** @{feedback.user.username}\n"
        f"**Type:** {feedback.feedback_type.capitalize()}\n"
        f"**Content:**\n{feedback.text_content}\n\n"
        f"_Action taken by @{admin_username}_")
    reply_markup = get_admin_buttons(feedback)

    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to update feedback notification: {e}")


async def notify_user_of_status_change(bot: Bot, feedback: Feedback):
    """Sends a DM to the user informing them of a status change."""
    status_text = feedback.status.replace("_", " ").capitalize()

    if feedback.feedback_type == 'question_report' and feedback.question:
        question_snippet = feedback.question.question_text[:50] + "..."
        if feedback.status == 'dismissed':
            message = f"Hi! Regarding the question you reported that starts with '{question_snippet}', our team has reviewed it. Thank you for helping us maintain our question quality!"
        else:
            message = f"Hi! The status of your report for the question starting with '{question_snippet}' has been updated to: **{status_text}**."
    else:
        message = f"Hi! The status of your feedback submission `#{feedback.id}` has been updated to: **{status_text}**."

    if feedback.status == 'in_progress':
        message += "\n\nOur team is now looking into it. Thank you for your contribution!"
    elif feedback.status == 'resolved':
        message += "\n\nThank you for helping us improve!"
    elif feedback.status == 'dismissed' and feedback.feedback_type != 'question_report':
        message += "\n\nThis feedback has been closed."

    try:
        await bot.send_message(chat_id=feedback.user.telegram_id, text=message, parse_mode="Markdown")
    except Forbidden:
        logger.warning(f"Failed to send status update to user {feedback.user.id}. They may have blocked the bot.")
    except Exception as e:
        logger.error(f"Failed to send status update to user {feedback.user.id}: {e}")


async def notify_admins_of_withdrawal(bot: Bot, feedback_id: int, user_username: str):
    """Notifies the admin group that a user has withdrawn a submission."""
    if not TELEGRAM_ADMIN_GROUP_ID:
        logger.warning("TELEGRAM_ADMIN_GROUP_ID not set. Cannot send withdrawal notification.")
        return

    text = f"⚠️ User @{user_username} has withdrawn their feedback submission `#{feedback_id}`."
    try:
        await bot.send_message(chat_id=TELEGRAM_ADMIN_GROUP_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to send withdrawal notification to admin group: {e}")

async def send_report_notification(bot: Bot, report_details: dict):
    """
    Sends a notification to the admin group about a new question report.
    """
    if not TELEGRAM_ADMIN_GROUP_ID:
        logger.warning("TELEGRAM_ADMIN_GROUP_ID not set. Cannot send report notification.")
        return

    # Truncate question text if it's too long to avoid hitting message limits
    question_text = report_details.get('question_text', 'N/A')
    if len(question_text) > 500:
        question_text = question_text[:500] + "..."

    text = (
        f"**🚨 New Question Report**\n\n"
        f"**User:** @{report_details.get('username', 'N/A')}\n"
        f"**Course:** `{report_details.get('course_name', 'N/A')}`\n"
        f"**Question ID:** `{report_details.get('question_id')}`\n"
        f"**Reason:** {report_details.get('reason', 'N/A').replace('_', ' ').capitalize()}\n\n"
        f"**Question Text:**\n"
        f"_{question_text}_"
    )

    # Assuming report_id is now passed in report_details
    report_id = report_details.get('report_id')
    question_id = report_details.get('question_id')

    keyboard = [
        [
            InlineKeyboardButton("View Question Details", callback_data=f"admin_view_question_{question_id}"),
            InlineKeyboardButton("Dismiss Report", callback_data=f"admin_dismiss_report_{report_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await bot.send_message(
            chat_id=TELEGRAM_ADMIN_GROUP_ID,
            text=text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        logger.info(f"Successfully sent question report notification for question {report_details.get('question_id')}")
    except Exception as e:
        logger.error(f"Failed to send question report notification to admin group: {e}")