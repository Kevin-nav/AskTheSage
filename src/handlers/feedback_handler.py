# src/handlers/feedback_handler.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from src.models.models import User, Feedback
from src.database import get_db
from src.services.notification_service import (
    send_new_feedback_notification,
    notify_admins_of_withdrawal,
)

# Setup logger
logger = logging.getLogger(__name__)

# Conversation states
(CHOOSE_TYPE, GET_TEXT, CONFIRM_SUBMISSION, VIEW_SUBMISSIONS, VIEW_SUBMISSION_DETAIL) = range(5)

# --- Entry Point ---
async def start_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the feedback conversation."""
    keyboard = [
        [InlineKeyboardButton("🐞 Report an Issue", callback_data="feedback_type_report")],
        [InlineKeyboardButton("💡 Suggest a Feature", callback_data="feedback_type_suggestion")],
        [InlineKeyboardButton("📝 View My Submissions", callback_data="feedback_view_submissions")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("How can I help you?", reply_markup=reply_markup)
    return CHOOSE_TYPE


# --- Helper Functions ---
async def get_user_from_telegram_id(telegram_id: int, session) -> User:
    """Fetches a user from the database by their Telegram ID."""
    return session.query(User).filter(User.telegram_id == telegram_id).first()


# --- Conversation Handlers ---

async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user choosing the feedback type or to view submissions."""
    query = update.callback_query
    await query.answer()

    if query.data == "feedback_view_submissions":
        return await view_submissions_list(update, context)

    feedback_type = query.data.replace("feedback_type_", "")
    context.user_data["feedback_type"] = feedback_type

    await query.edit_message_text(text=f"You've chosen to submit a {feedback_type}. Please send me the detailed text of your feedback.")
    return GET_TEXT

async def get_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the feedback text and asks for confirmation."""
    text_content = update.message.text
    context.user_data["text_content"] = text_content
    feedback_type = context.user_data["feedback_type"]

    escaped_content = escape_markdown(text_content, version=2)
    summary = f"**Type:** {feedback_type.capitalize()}\n" \
              f"**Content:**\n{escaped_content}"

    keyboard = [
        [InlineKeyboardButton("✅ Submit", callback_data="confirm_submit")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_submission")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Please review your submission:\n\n{summary}",
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    return CONFIRM_SUBMISSION

async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the feedback to the database and notifies admins."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_submission":
        await query.edit_message_text(text="Submission canceled.")
        return ConversationHandler.END

    feedback_type = context.user_data["feedback_type"]
    text_content = context.user_data["text_content"]
    telegram_id = update.effective_user.id
    user_username = update.effective_user.username or "N/A"

    with get_db() as session:
        user = await get_user_from_telegram_id(telegram_id, session)
        if not user:
            await query.edit_message_text(text="Could not find your user profile. Please use /start first.")
            return ConversationHandler.END

        new_feedback = Feedback(
            user_id=user.id,
            feedback_type=feedback_type,
            text_content=text_content,
        )
        session.add(new_feedback)
        session.commit()
        # Eagerly load the user relationship so it's available outside the session
        session.refresh(new_feedback)
        feedback_id = new_feedback.id

    await query.edit_message_text(text=f"Thank you! Your feedback has been submitted successfully (ID: #{feedback_id}).")

    # Trigger admin notification
    await send_new_feedback_notification(context.bot, new_feedback, user_username)

    return ConversationHandler.END


# --- View and Withdraw Handlers ---

async def view_submissions_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays a list of the user's past submissions."""
    query = update.callback_query
    if query:
        await query.answer()

    telegram_id = update.effective_user.id
    with get_db() as session:
        user = await get_user_from_telegram_id(telegram_id, session)
        if not user:
            await update.effective_message.reply_text("Could not find your user profile. Please use /start first.")
            return ConversationHandler.END

        submissions = session.query(Feedback).filter(Feedback.user_id == user.id).order_by(Feedback.created_at.desc()).all()

    if not submissions:
        await update.effective_message.edit_text("You have not submitted any feedback yet.")
        return ConversationHandler.END

    keyboard = []
    for sub in submissions:
        status_icon = "✅" if sub.is_withdrawn else ("⏳" if sub.status == 'open' else "▶️" if sub.status == 'in_progress' else "✔️")
        snippet = sub.text_content[:30]
        button_text = f"{status_icon} #{sub.id}: {snippet}..."
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_detail_{sub.id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.edit_text("Here are your submissions. Select one to view details.", reply_markup=reply_markup)
    return VIEW_SUBMISSIONS

async def view_submission_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Displays the full detail of a single submission."""
    query = update.callback_query
    await query.answer()

    feedback_id = int(query.data.replace("view_detail_", ""))

    with get_db() as session:
        feedback = session.query(Feedback).filter(Feedback.id == feedback_id).first()

    if not feedback:
        await query.edit_message_text("Sorry, I couldn't find that feedback item.")
        return VIEW_SUBMISSIONS

    # Format the message - escape ALL dynamic content for MarkdownV2
    escaped_content = escape_markdown(feedback.text_content, version=2)
    escaped_feedback_id = escape_markdown(f"#{feedback.id}", version=2)
    escaped_type = escape_markdown(feedback.feedback_type.capitalize(), version=2)
    escaped_status = escape_markdown(feedback.status.capitalize(), version=2)
    escaped_date = escape_markdown(feedback.created_at.strftime('%Y-%m-%d %H:%M'), version=2)
    
    text = (
        f"**Feedback {escaped_feedback_id}**\n"
        f"**Type:** {escaped_type}\n"
        f"**Status:** {escaped_status}\n"
        f"**Submitted:** {escaped_date}\n\n"
        f"**Content:**\n{escaped_content}"
    )
    if feedback.is_withdrawn:
        text += "\n\n**This submission has been withdrawn\\.**"

    keyboard = [[InlineKeyboardButton("⬅️ Back to List", callback_data="back_to_list")]]

    # Add withdraw button if applicable
    if feedback.status == 'open' and not feedback.is_withdrawn:
        keyboard.insert(0, [InlineKeyboardButton("🗑️ Withdraw Submission", callback_data=f"withdraw_{feedback.id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="MarkdownV2")
    return VIEW_SUBMISSION_DETAIL





async def withdraw_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles withdrawing a submission."""
    query = update.callback_query
    await query.answer()

    feedback_id = int(query.data.replace("withdraw_", ""))
    user_username = update.effective_user.username or "N/A"

    with get_db() as session:
        feedback = session.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            await query.edit_message_text("Sorry, I couldn't find that feedback item.")
            return VIEW_SUBMISSIONS

        feedback.is_withdrawn = True
        session.commit()

    await query.edit_message_text(f"Submission #{feedback_id} has been withdrawn.")
    await notify_admins_of_withdrawal(context.bot, feedback_id, user_username)

    return ConversationHandler.END

# --- Cancel Function ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    # This is called by the /cancel command
    await update.message.reply_text("Feedback process canceled.")
    context.user_data.clear()
    return ConversationHandler.END


def get_feedback_conversation_handler() -> ConversationHandler:
    """Creates the feedback conversation handler."""
    return ConversationHandler(
        entry_points=[CommandHandler("feedback", start_feedback)],
        states={
            CHOOSE_TYPE: [CallbackQueryHandler(choose_type)],
            GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_text)],
            CONFIRM_SUBMISSION: [CallbackQueryHandler(confirm_submission)],
            VIEW_SUBMISSIONS: [CallbackQueryHandler(view_submission_detail, pattern="^view_detail_")],
            VIEW_SUBMISSION_DETAIL: [
                CallbackQueryHandler(withdraw_submission, pattern="^withdraw_"),
                CallbackQueryHandler(view_submissions_list, pattern="^back_to_list$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
