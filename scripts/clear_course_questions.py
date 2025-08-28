import os
import logging
import sys

# Add root directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db
from src.models.models import Course, Question, UserAnswer, QuizSessionQuestion

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

COURSE_NAME_TO_CLEAR = "Basic Electronics"

def clear_course_questions():
    """
    Deletes all questions and related user answers for a specific course.
    """
    with get_db() as db:
        # Find the course
        course_to_clear = db.query(Course).filter(Course.name == COURSE_NAME_TO_CLEAR).first()

        if not course_to_clear:
            logging.error(f"Course '{COURSE_NAME_TO_CLEAR}' not found. No questions were deleted.")
            return

        logging.info(f"Found course '{course_to_clear.name}' (ID: {course_to_clear.id}). Preparing to delete questions.")

        # Get all question IDs for the course
        question_ids_to_delete = [q.id for q in db.query(Question.id).filter_by(course_id=course_to_clear.id).all()]

        if not question_ids_to_delete:
            logging.info(f"No questions found for course '{COURSE_NAME_TO_CLEAR}'. Nothing to delete.")
            return

        logging.info(f"Found {len(question_ids_to_delete)} questions to delete.")

        # 1. Delete related UserAnswer records
        deleted_answers_count = db.query(UserAnswer).filter(UserAnswer.question_id.in_(question_ids_to_delete)).delete(synchronize_session=False)
        logging.info(f"Deleted {deleted_answers_count} related user answers.")

        # 2. Delete related QuizSessionQuestion records
        deleted_quiz_session_questions_count = db.query(QuizSessionQuestion).filter(QuizSessionQuestion.question_id.in_(question_ids_to_delete)).delete(synchronize_session=False)
        logging.info(f"Deleted {deleted_quiz_session_questions_count} related quiz session questions.")

        # 3. Delete the questions themselves
        deleted_questions_count = db.query(Question).filter_by(course_id=course_to_clear.id).delete(synchronize_session=False)
        logging.info(f"Deleted {deleted_questions_count} questions for course '{COURSE_NAME_TO_CLEAR}'.")

        db.commit()
        logging.info("Deletion complete and committed to the database.")

if __name__ == "__main__":
    clear_course_questions()
