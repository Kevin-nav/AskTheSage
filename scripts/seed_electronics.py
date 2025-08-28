import os
import json
import logging
import sys

# Add root directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db
from src.models.models import Course, Question

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_electronics_questions():
    """
    Deletes all existing 'Basic Electronics' questions and re-loads them
    from the structured JSON file.
    """
    # Construct the absolute path to the JSON file
    json_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'formatted_questions',
        'basic_electronics_structured.json'
    )

    if not os.path.exists(json_path):
        logging.error(f"JSON file not found at: {json_path}")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            questions_data = json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {json_path}: {e}")
        return

    with get_db() as db:
        electronics_course = db.query(Course).filter(Course.name == "Basic Electronics").first()

        if not electronics_course:
            logging.error("Course 'Basic Electronics' not found in the database.")
            logging.error("Please ensure the course is created before running this script.")
            return

        logging.info(f"Found course '{electronics_course.name}' with ID: {electronics_course.id}")
        
        # --- Delete all existing questions for this course ---
        try:
            num_deleted = db.query(Question).filter(Question.course_id == electronics_course.id).delete()
            db.commit()
            if num_deleted > 0:
                logging.info(f"Successfully deleted {num_deleted} old questions for '{electronics_course.name}'.")
            else:
                logging.info("No old questions found to delete.")
        except Exception as e:
            db.rollback()
            logging.error(f"An error occurred while deleting old questions: {e}")
            return
        
        # --- Load new questions from JSON ---
        questions_added = 0
        for q_data in questions_data:
            try:
                if q_data['correct_answer_index'] == -1:
                    logging.warning(f"Skipping question with no correct answer: {q_data['question_text'][:50]}...")
                    continue

                correct_answer_text = q_data['options'][q_data['correct_answer_index']]
                
                new_question = Question(
                    course_id=electronics_course.id,
                    question_text=q_data['question_text'],
                    options=q_data['options'],
                    correct_answer=correct_answer_text,
                    explanation=q_data['explanation'],
                    has_latex=q_data.get('has_latex', False)
                )
                db.add(new_question)
                questions_added += 1
            except IndexError:
                logging.error(f"Invalid 'correct_answer_index' for question: {q_data['question_text'][:50]}...")
            except Exception as e:
                logging.error(f"An error occurred while processing question: {q_data['question_text'][:50]}... Error: {e}")

        if questions_added > 0:
            db.commit()
            logging.info(f"Successfully added {questions_added} new questions for Basic Electronics.")
        else:
            logging.info("No new questions were added for Basic Electronics.")

if __name__ == "__main__":
    load_electronics_questions()
