import os
import sys
import logging
from sqlalchemy import func, desc, asc

# Add root directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db
from src.models.models import Question, Course

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Minimum number of attempts for a question to be included in the analysis
MIN_ATTEMPTS_THRESHOLD = 5

# Number of top questions to show in each category
TOP_N = 10

def analyze_question_performance():
    """Analyzes the global performance of questions and prints a report."""
    with get_db() as db:
        logger.info("Starting question performance analysis...")
        logger.info(f"Minimum attempt threshold: {MIN_ATTEMPTS_THRESHOLD}")
        logger.info(f"Reporting top {TOP_N} questions per category.")

        # --- Most Difficult Questions (Highest Incorrect Rate) ---
        most_difficult_questions = (
            db.query(
                Question.id,
                Question.question_text,
                Course.name.label('course_name'),
                Question.total_attempts,
                Question.total_incorrect,
                (Question.total_incorrect * 100.0 / Question.total_attempts).label('incorrect_rate')
            )
            .join(Course, Question.course_id == Course.id)
            .filter(Question.total_attempts >= MIN_ATTEMPTS_THRESHOLD)
            .order_by(desc('incorrect_rate'))
            .limit(TOP_N)
            .all()
        )

        # --- Most Failed Questions (Highest Number of Incorrect Answers) ---
        most_failed_questions = (
            db.query(
                Question.id,
                Question.question_text,
                Course.name.label('course_name'),
                Question.total_attempts,
                Question.total_incorrect
            )
            .join(Course, Question.course_id == Course.id)
            .filter(Question.total_attempts >= MIN_ATTEMPTS_THRESHOLD)
            .order_by(desc(Question.total_incorrect))
            .limit(TOP_N)
            .all()
        )

        # --- Easiest Questions (Lowest Incorrect Rate) ---
        easiest_questions = (
            db.query(
                Question.id,
                Question.question_text,
                Course.name.label('course_name'),
                Question.total_attempts,
                Question.total_incorrect,
                (Question.total_incorrect * 100.0 / Question.total_attempts).label('incorrect_rate')
            )
            .join(Course, Question.course_id == Course.id)
            .filter(Question.total_attempts >= MIN_ATTEMPTS_THRESHOLD)
            .order_by(asc('incorrect_rate'))
            .limit(TOP_N)
            .all()
        )

        # --- Print the Report ---
        print("\n" + "="*80)
        print("QUESTION PERFORMANCE ANALYSIS REPORT")
        print("="*80)

        print(f"\n--- 📈 Top {TOP_N} Most Difficult Questions (by % incorrect) ---")
        if most_difficult_questions:
            for q in most_difficult_questions:
                print(f"  - ID: {q.id} | Course: {q.course_name} | Incorrect: {q.incorrect_rate:.2f}% ({q.total_incorrect}/{q.total_attempts} attempts)")
                print(f"    Text: {q.question_text[:100]}...")
        else:
            print("  No questions met the threshold for this category.")

        print(f"\n--- 📉 Top {TOP_N} Most Failed Questions (by # of failures) ---")
        if most_failed_questions:
            for q in most_failed_questions:
                print(f"  - ID: {q.id} | Course: {q.course_name} | Incorrect: {q.total_incorrect} times ({q.total_attempts} attempts)")
                print(f"    Text: {q.question_text[:100]}...")
        else:
            print("  No questions met the threshold for this category.")

        print(f"\n--- ✅ Top {TOP_N} Easiest Questions (by % incorrect) ---")
        if easiest_questions:
            for q in easiest_questions:
                print(f"  - ID: {q.id} | Course: {q.course_name} | Incorrect: {q.incorrect_rate:.2f}% ({q.total_incorrect}/{q.total_attempts} attempts)")
                print(f"    Text: {q.question_text[:100]}...")
        else:
            print("  No questions met the threshold for this category.")
        
        print("\n" + "="*80)
        logger.info("Analysis complete.")

if __name__ == "__main__":
    analyze_question_performance()
