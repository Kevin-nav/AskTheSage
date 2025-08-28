import os
import csv
import logging
import sys
import json
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from pathlib import Path

# Add root directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db
from src.models.models import Question, Course

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#EXPORTED_DATA_DIR = Path(__file__).parent / "exported_data"

PROJECT_ROOT = Path(__file__).parent.parent # Added
EXPORTED_DATA_DIR = PROJECT_ROOT / "exported_data" # Modified


def clear_course_questions(course_name: str):
    """Deletes all questions for a specific course."""
    with get_db() as db:
        logger.info(f"Querying for course: '{course_name}' to clear existing questions.")
        course = db.query(Course).filter(Course.name == course_name).first()

        if not course:
            logger.error(f"Course '{course_name}' not found. Cannot clear questions.")
            return

        questions_to_delete = db.query(Question).filter(Question.course_id == course.id).all()
        
        if not questions_to_delete:
            logger.info(f"No existing questions found for course '{course_name}'. Nothing to clear.")
            return

        logger.info(f"Deleting {len(questions_to_delete)} questions for course '{course_name}'.")
        db.query(Question).filter(Question.course_id == course.id).delete(synchronize_session=False)
        db.commit()
        logger.info("Successfully deleted old questions.")


def load_questions_from_csv(course_name: str, csv_file_path: Path):
    """Loads questions for a specific course from a CSV file."""
    clear_course_questions(course_name)

    with get_db() as db:
        logger.info(f"Querying for course: '{course_name}'")
        course = db.query(Course).filter(Course.name == course_name).first()

        if not course:
            logger.error(f"Course '{course_name}' not found. Cannot load questions.")
            return

        if not csv_file_path.exists():
            logger.error(f"CSV file not found at: {csv_file_path}")
            return

        logger.info(f"Loading questions from {csv_file_path}...")

        try:
            with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                questions_to_add = []
                for row in reader:
                    try:
                        options = json.loads(row['options']) if row['options'] else None
                        
                        # Handle empty strings for URLs by converting them to None
                        image_url = row['image_url'] if row['image_url'] else None
                        explanation_image_url = row['explanation_image_url'] if row['explanation_image_url'] else None

                        new_question = Question(
                            id=int(row['id']),
                            course_id=course.id, # Use the queried course_id
                            question_text=row['question_text'],
                            options=options,
                            correct_answer=row['correct_answer'],
                            explanation=row['explanation'],
                            has_latex=row['has_latex'].lower() in ['true', '1', 't'],
                            difficulty_score=float(row['difficulty_score']) if row['difficulty_score'] else None,
                            image_url=image_url,
                            explanation_image_url=explanation_image_url
                        )
                        questions_to_add.append(new_question)
                    except (json.JSONDecodeError, ValueError, KeyError) as e:
                        logger.error(f"Skipping row due to parsing error: {row}. Error: {e}")
                        continue
            
            if questions_to_add:
                # Since we are specifying IDs, we need to merge them carefully.
                # A simple bulk_insert_mappings won't work with existing IDs without more complex logic.
                # Let's merge each question individually.
                logger.info(f"Adding/updating {len(questions_to_add)} questions in the database.")
                for q in questions_to_add:
                    db.merge(q)
                db.commit()
                logger.info(f"\033[92mSuccessfully loaded questions from {csv_file_path}\033[0m")
            else:
                logger.warning("No questions were loaded from the CSV file.")

        except IOError as e:
            logger.error(f"Failed to read CSV file {csv_file_path}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    with get_db() as db:
        # --- Step 1: Select CSV File ---
        csv_files = list(EXPORTED_DATA_DIR.glob("*.csv"))
        if not csv_files:
            logger.info(f"No CSV files found in {EXPORTED_DATA_DIR}. Please export some questions first.")
            sys.exit(0)

        print("\nAvailable CSV files to load from:")
        for i, csv_file in enumerate(csv_files):
            print(f"{i + 1}. {csv_file.name}")

        selected_csv_path = None
        while True:
            try:
                csv_choice = input("Enter the number of the CSV file to load (or 'q' to quit): ")
                if csv_choice.lower() == 'q':
                    print("Exiting script.")
                    sys.exit(0)

                csv_index = int(csv_choice) - 1
                if 0 <= csv_index < len(csv_files):
                    selected_csv_path = csv_files[csv_index]
                    break
                else:
                    print("Invalid choice. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number or 'q'.")

        # --- Step 2: Select Course to Load Into ---
        courses = db.query(Course).all()
        if not courses:
            logger.info("No courses found in the database. Please create courses first.")
            sys.exit(0)

        course_options = []
        print("\nAvailable Courses to load questions into:")
        for i, course in enumerate(courses):
            question_count = db.query(Question).filter(Question.course_id == course.id).count()
            course_options.append((course.name, question_count))
            print(f"{i + 1}. {course.name} (Current questions: {question_count})")

        selected_course_name = None
        while True:
            try:
                course_choice = input("Enter the number of the course to load questions into (or 'q' to quit): ")
                if course_choice.lower() == 'q':
                    print("Exiting script.")
                    sys.exit(0)

                course_index = int(course_choice) - 1
                if 0 <= course_index < len(course_options):
                    selected_course_name = course_options[course_index][0]
                    break
                else:
                    print("Invalid choice. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number or 'q'.")

        # --- Step 3: Execute Load Operation ---
        if selected_csv_path and selected_course_name:
            load_questions_from_csv(selected_course_name, selected_csv_path)
        else:
            logger.error("CSV file or Course not selected. Exiting.")
