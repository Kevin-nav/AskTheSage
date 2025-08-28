from telegram import Update
from telegram.ext import ContextTypes

from src.config import WELCOME_MESSAGE
from src.database import get_db
from src.services import quiz_service

HELP_MESSAGE = """
Here's how to use the bot:

/quiz - Start a new quiz. I'll guide you through selecting a course and the number of questions. The questions will be adapted based on your performance.

/cancel - Use this at any time during a quiz to stop it. Your progress on that quiz will be saved.

/performance - See your quiz performance over time, including average scores and recent quiz results.

/help - Show this message again.

I will adapt to your performance to help you focus on your weak spots. Happy studying!
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a detailed help message when the /help command is issued."""
    await update.message.reply_text(HELP_MESSAGE)

async def performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's quiz performance over time."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    with get_db() as db:
        performance_data = quiz_service.get_user_performance_data(db, user_id)

    total_quizzes = performance_data["total_quizzes"]
    overall_average_score = performance_data["overall_average_score"]
    categorized_performance = performance_data["categorized_performance"]
    other_courses_performance = performance_data["other_courses_performance"]

    message_parts = ["✨ Your Quiz Journey So Far! ✨\n"]
    message_parts.append(f"Total Quizzes Completed: **{total_quizzes}**")
    
    overall_avg_score_message = f"Overall Average Score: **{overall_average_score:.0f}%** "
    if overall_average_score >= 90:
        overall_avg_score_message += "- Outstanding! Keep shining! 🌟"
    elif overall_average_score >= 75:
        overall_avg_score_message += "- Great work! You're mastering it! 💪"
    elif overall_average_score >= 50:
        overall_avg_score_message += "- Good progress! Keep pushing forward! 👍"
    else:
        overall_avg_score_message += "- Every step counts! Let's learn and grow! 🌱"
    message_parts.append(overall_avg_score_message + "\n")

    if categorized_performance:
        message_parts.append("🎓 Performance by Faculty & Program: ")
        for faculty_name, programs_data in categorized_performance.items():
            message_parts.append(f"\n**Faculty: {faculty_name}**")
            for program_name, courses_data in programs_data.items():
                message_parts.append(f"  **Program: {program_name}**")
                for course_name, data in courses_data.items():
                    message_parts.append(f"    - **{course_name}**")
                    message_parts.append(f"      Quizzes: {data["total_quizzes_in_course"]}")
                    
                    course_avg_score = data["average_score_in_course"]
                    course_avg_score_message = f"      Average Score: {course_avg_score:.0f}% "
                    if course_avg_score >= 90:
                        course_avg_score_message += "- Excellent!"
                    elif course_avg_score >= 75:
                        course_avg_score_message += "- Very Good!"
                    elif course_avg_score >= 50:
                        course_avg_score_message += "- Keep Going!"
                    else:
                        course_avg_score_message += "- Focus Area!"
                    message_parts.append(course_avg_score_message)

                    if data["recent_quizzes_in_course"]:
                        message_parts.append("      Recent Scores:")
                        for entry in data["recent_quizzes_in_course"]:
                            message_parts.append(f"        - {entry["score"]:.0f}% on {entry["date"]}")
                    else:
                        message_parts.append("        No recent scores for this course.")
    
    if other_courses_performance:
        message_parts.append("\n🌍 Courses Outside Your Preferred Program: ")
        for course_name, data in other_courses_performance.items():
            message_parts.append(f"\n  - **{course_name}**")
            message_parts.append(f"    Quizzes: {data["total_quizzes_in_course"]}")
            
            course_avg_score = data["average_score_in_course"]
            course_avg_score_message = f"    Average Score: {course_avg_score:.0f}% "
            if course_avg_score >= 90:
                course_avg_score_message += "- Excellent!"
            elif course_avg_score >= 75:
                course_avg_score_message += "- Very Good!"
            elif course_avg_score >= 50:
                course_avg_score_message += "- Keep Going!"
            else:
                course_avg_score_message += "- Focus Area!"
            message_parts.append(course_avg_score_message)

            if data["recent_quizzes_in_course"]:
                message_parts.append("    Recent Scores:")
                for entry in data["recent_quizzes_in_course"]:
                    message_parts.append(f"      - {entry["score"]:.0f}% on {entry["date"]}")
            else:
                message_parts.append("      No recent scores for this course.")

    if not categorized_performance and not other_courses_performance:
        message_parts.append("No detailed course performance to display. Time to start a new /quiz! 🚀")

    await context.bot.send_message(chat_id=chat_id, text="\n".join(message_parts), parse_mode='Markdown')