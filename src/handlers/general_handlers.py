from telegram import Update
from telegram.ext import ContextTypes

from src.config import WELCOME_MESSAGE, ADMIN_USERNAMES
from src.database import get_db
from src.models.models import User
from src.adaptive_learning.service import AdaptiveQuizService

HELP_MESSAGE = """
Here's how to use the bot:

/quiz - Start a new quiz. I'll guide you through selecting a course and the number of questions. The questions will be adapted based on your performance.

/cancel - Use this at any time during a quiz to stop it. Your progress on that quiz will be saved.

/performance - See your quiz performance over time, including average scores and recent quiz results.

/help - Show this message again.

I will adapt to your performance to help you focus on your weak spots. Happy studying!
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and ensures the user exists in the database."""
    telegram_user = update.effective_user
    welcome_text = f"Welcome to AskTheSageQuizzer, {telegram_user.first_name}!"
    
    with get_db() as session:
        db_user = session.query(User).filter(User.telegram_id == telegram_user.id).first()

        if not db_user:
            db_user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                is_admin=False
            )
            session.add(db_user)
            if telegram_user.username and telegram_user.username in ADMIN_USERNAMES:
                db_user.is_admin = True
            session.commit()
            await update.message.reply_text(f"{welcome_text}\n" + WELCOME_MESSAGE)
        else:
            welcome_text = f"Welcome back to AskTheSageQuizzer, {telegram_user.first_name}!"
            if db_user.username != telegram_user.username:
                db_user.username = telegram_user.username
            if telegram_user.username and telegram_user.username in ADMIN_USERNAMES and not db_user.is_admin:
                db_user.is_admin = True
            session.commit()
            await update.message.reply_text(f"{welcome_text}\n" + WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a detailed help message when the /help command is issued."""
    await update.message.reply_text(HELP_MESSAGE)

async def performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's new, comprehensive performance report."""
    telegram_id = update.effective_user.id
    
    with get_db() as db:
        service = AdaptiveQuizService(db)
        performance_data = service.get_user_performance_data(telegram_id)

    if performance_data.get("status") != "success":
        await update.message.reply_text("Could not retrieve your performance data. Have you completed a quiz yet?")
        return

    # --- Part 1: Overall Performance ---
    lifetime_stats = performance_data.get("lifetime_stats", {})
    total_answered = lifetime_stats.get("total_answered", 0)
    total_correct = lifetime_stats.get("total_correct", 0)

    message_parts = ["✨ **Your Quiz Journey So Far!** ✨\n"]
    message_parts.append("🧠 **Overall Performance**")
    if total_answered > 0:
        overall_accuracy = (total_correct / total_answered) * 100
        message_parts.append(f"- Accuracy: {overall_accuracy:.1f}%")
        message_parts.append(f"- Total Questions Attempted: {total_answered}")
        message_parts.append(f"- Total Correct Questions: {total_correct}")
    else:
        message_parts.append("No questions answered yet. Time to start a /quiz! 🚀")

    message_parts.append("\n" + ("-" * 25) + "\n")

    # --- Part 2: Categorized Course Performance ---
    categorized_performance = performance_data.get("categorized_performance", {})
    preferred_courses = categorized_performance.get("preferred_courses", [])
    other_courses = categorized_performance.get("other_courses", [])

    if preferred_courses or other_courses:
        if preferred_courses:
            message_parts.append("🎓 **Performance in Your Program**")
            for course in preferred_courses:
                message_parts.append(f"- _{course['course_name']}_: {course['accuracy']:.1f}% Accuracy")
            message_parts.append("")

        if other_courses:
            message_parts.append("🌍 **Performance in Other Courses**")
            for course in other_courses:
                message_parts.append(f"- _{course['course_name']}_: {course['accuracy']:.1f}% Accuracy")
            message_parts.append("")
    
    message_parts.append("-" * 25 + "\n")

    # --- Part 3: Recent Activity ---
    recent_quizzes = performance_data.get("recent_quizzes", [])
    if recent_quizzes:
        message_parts.append("🕒 **Recent Activity:**")
        status_map = {
            'completed': '(Completed)',
            'incomplete': '(Ended Early)',
            'cancelled': '(Stopped by You)'
        }
        for quiz in recent_quizzes:
            score_fraction = f"{quiz['correct_count']}/{quiz['answered_count']}"
            status_text = status_map.get(quiz['status'], '(Finished)')
            message_parts.append(f"- _{quiz['course_name']}_: **{score_fraction}** {status_text}")

    message = "\n".join(message_parts)
    await update.message.reply_text(message, parse_mode='Markdown')

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles any command that is not recognized."""
    await update.message.reply_text("Sorry, I didn't understand that command. Please use /help to see what I can do.")
