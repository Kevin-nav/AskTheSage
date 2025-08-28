import os
import csv
import logging
import sys
import json
import argparse # Added import for argparse

# Add root directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db
from src.models.models import Question, Course

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = "exported_data"

def export_course_questions_to_csv(course_name_to_export: str):
    """Fetches all questions for a specific course and exports them to a CSV file."""
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_filename = os.path.join(OUTPUT_DIR, f"{course_name_to_export.lower().replace(' ', '_')}_questions.csv")

    with get_db() as db:
        logger.info(f"Querying for course: '{course_name_to_export}'")
        course = db.query(Course).filter(Course.name == course_name_to_export).first()

        if not course:
            logger.error(f"Course '{course_name_to_export}' not found. Cannot export questions.")
            return

        questions = db.query(Question).filter(Question.course_id == course.id).order_by(Question.id).all()

        if not questions:
            logger.warning(f"No questions found for course '{course_name_to_export}'. An empty CSV will be created.")

        logger.info(f"Found {len(questions)} questions to export. Writing to {output_filename}...")

        # Define the headers for the CSV file
        headers = [
            'id', 'course_id', 'question_text', 'options', 'correct_answer',
            'explanation', 'has_latex', 'difficulty_score', 'image_url',
            'explanation_image_url'
        ]

        try:
            with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)

                for q in questions:
                    writer.writerow([
                        q.id,
                        q.course_id,
                        q.question_text,
                        json.dumps(q.options), # Convert JSON object to string
                        q.correct_answer,
                        q.explanation,
                        q.has_latex,
                        q.difficulty_score,
                        q.image_url,
                        q.explanation_image_url
                    ])
            logger.info(f"\033[92mSuccessfully exported questions to {output_filename}\033[0m")
        except IOError as e:
            logger.error(f"Failed to write to CSV file {output_filename}: {e}", exc_info=True)

if __name__ == "__main__":
    with get_db() as db:
        courses = db.query(Course).all()
        if not courses:
            logger.info("No courses found in the database.")
            sys.exit(0)

        course_options = []
        print("\nAvailable Courses:")
        for i, course in enumerate(courses):
            question_count = db.query(Question).filter(Question.course_id == course.id).count()
            course_options.append((course.name, question_count))
            print(f"{i + 1}. {course.name} ({question_count} questions)")

        while True:
            try:
                choice = input("Enter the number of the course to export (or 'q' to quit): ")
                if choice.lower() == 'q':
                    print("Exiting export script.")
                    sys.exit(0)

                choice_index = int(choice) - 1
                if 0 <= choice_index < len(course_options):
                    selected_course_name = course_options[choice_index][0]
                    export_course_questions_to_csv(selected_course_name)
                    break
                else:
                    print("Invalid choice. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number or 'q'.")
