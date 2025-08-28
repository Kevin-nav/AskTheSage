import os
import json
import logging
import argparse
import re
from pathlib import Path
import tempfile
import subprocess
import shutil
import boto3
from botocore.exceptions import ClientError
import hashlib
import time
from typing import List, Dict, Any, Optional
import sys

# Add project root to path to allow imports from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import get_db
from src.models.models import Course, Question
from src.config import S3_BUCKET_NAME, AWS_REGION
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.services.rendering_service import MCQImageRenderer, MCQQuestion # Added imports

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('question_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class QuestionManager:
    def __init__(self, dry_run: bool = False, force_render: bool = False):
        self.dry_run = dry_run
        self.force_render = force_render
        self.s3_client = boto3.client('s3', region_name=AWS_REGION)
        self.mcq_image_renderer = MCQImageRenderer() # Initialize MCQImageRenderer
        self.stats = {
            'processed': 0, 'added': 0, 'updated': 0, 'skipped': 0, 'rendered': 0,
            'cached_render': 0, 'failed_render': 0, 'start_time': time.time()
        }
        self._validate_environment()

    def _validate_environment(self):
        convert_exe = 'magick' if os.sys.platform == 'win32' else 'convert'
        required_tools = ['pdflatex', convert_exe]
        if not all(shutil.which(tool) for tool in required_tools):
            logger.warning(f"Missing required tools: {required_tools}. LaTeX rendering might fail. Install TeX Live and ImageMagick.")
        try:
            self.s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix='rendered-cache/', MaxKeys=1)
            logger.info("S3 connectivity and permissions verified successfully")
        except Exception as e:
            logger.warning(f"S3 connectivity failed: {e}. S3 uploads will not work.")

    def _format_options(self, options_list: List[str]) -> Dict[str, str]:
        """Formats a list of options into a dictionary (A, B, C, ...)."""
        return {chr(65 + i): option for i, option in enumerate(options_list)}

    def _generate_question_hash(self, question_data: Dict[str, Any]) -> str:
        """Generates a unique hash for a question based on its core content using MCQQuestion."""
        # Create a temporary MCQQuestion to leverage its ID generation
        temp_mcq_question = MCQQuestion(
            question_text=question_data['question_text'],
            options=question_data['options'],
            correct_answer_index=question_data.get('correct_answer_index', 0), # Default to 0 if not present for hashing
            explanation=question_data.get('explanation', ''),
            has_latex=question_data.get('has_latex', False)
        )
        return temp_mcq_question.question_id

    def _process_single_question(self, db: Session, course: Course, q_data: Dict[str, Any], existing_question: Optional[Question] = None) -> Optional[Question]:
        self.stats['processed'] += 1

        question_text = q_data['question_text']
        options_list = q_data['options']
        explanation = q_data.get('explanation')
        has_latex = q_data.get('has_latex', False)

        image_url = None
        explanation_image_url = None

        if has_latex:
            # Create MCQQuestion object for the new renderer
            mcq_question = MCQQuestion(
                question_text=question_text,
                options=options_list,
                correct_answer_index=q_data['correct_answer_index'],
                explanation=explanation,
                has_latex=has_latex,
                course=course.name,
                topic=q_data.get('topic', '') # Assuming 'topic' might be in q_data
            )

            # Render question and explanation to local files using MCQImageRenderer
            local_question_path, local_explanation_path = self.mcq_image_renderer.render_question(mcq_question, question_number=self.stats['processed'])

            # Upload to S3 if rendering was successful
            if local_question_path and os.path.exists(local_question_path):
                s3_key_q = f"rendered-cache/{mcq_question.question_id}_q.png"
                if not self.dry_run:
                    with open(local_question_path, 'rb') as f:
                        self.s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key_q, Body=f.read(), ContentType='image/png')
                    image_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key_q}"
                    logger.info(f"Uploaded question image to S3: {image_url}")
                else:
                    image_url = "DRY_RUN_S3_URL_Q"
                    logger.info(f"[DRY RUN] Would upload question image to S3: {s3_key_q}")
                # Clean up local file after upload
                if os.path.exists(local_question_path):
                    os.remove(local_question_path)

            if local_explanation_path and os.path.exists(local_explanation_path):
                s3_key_e = f"rendered-cache/{mcq_question.question_id}_e.png"
                if not self.dry_run:
                    with open(local_explanation_path, 'rb') as f:
                        self.s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key_e, Body=f.read(), ContentType='image/png')
                    explanation_image_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key_e}"
                    logger.info(f"Uploaded explanation image to S3: {explanation_image_url}")
                else:
                    explanation_image_url = "DRY_RUN_S3_URL_E"
                    logger.info(f"[DRY RUN] Would upload explanation image to S3: {s3_key_e}")
                # Clean up local file after upload
                if os.path.exists(local_explanation_path):
                    os.remove(local_explanation_path)

        if q_data['correct_answer_index'] == -1:
            logger.warning(f"Skipping question with no correct answer: {question_text[:50]}...")
            self.stats['skipped'] += 1
            return None

        correct_answer_text = options_list[q_data['correct_answer_index']]
        formatted_opts = self._format_options(options_list)

        if existing_question:
            # Update existing question
            if self.dry_run:
                logger.info(f"[DRY RUN] Would update question ID {existing_question.id}: {question_text[:50]}...")
                self.stats['updated'] += 1
                return existing_question

            existing_question.question_text = question_text
            existing_question.options = formatted_opts
            existing_question.correct_answer = correct_answer_text
            existing_question.explanation = explanation
            existing_question.has_latex = has_latex
            existing_question.difficulty_score = q_data.get('difficulty_score')
            existing_question.image_url = image_url
            existing_question.explanation_image_url = explanation_image_url
            db.add(existing_question)
            logger.info(f"Updated question ID {existing_question.id}: {question_text[:50]}...")
            self.stats['updated'] += 1
            return existing_question
        else:
            # Add new question
            if self.dry_run:
                logger.info(f"[DRY RUN] Would add new question: {question_text[:50]}...")
                self.stats['added'] += 1
                return None # In dry run, we don't create a real object

            new_question = Question(
                course_id=course.id,
                question_text=question_text,
                options=formatted_opts,
                correct_answer=correct_answer_text,
                explanation=explanation,
                has_latex=has_latex,
                difficulty_score=q_data.get('difficulty_score'),
                image_url=image_url,
                explanation_image_url=explanation_image_url
            )
            db.add(new_question)
            logger.info(f"Added new question for '{course.name}': {question_text[:50]}...")
            self.stats['added'] += 1
            return new_question

    def add_questions(self, course_name: str, json_file_path: str):
        """Adds new questions, skipping duplicates based on content hash."""
        logger.info(f"Starting 'add' operation for course '{course_name}' from '{json_file_path}'")
        questions_data = self._load_json_data(json_file_path)
        if not questions_data: return

        with get_db() as db:
            course = db.query(Course).filter(Course.name == course_name).first()
            if not course:
                logger.error(f"Course '{course_name}' not found. Please create it first.")
                return

            existing_question_hashes = {self._generate_question_hash(q.to_dict()): q for q in db.query(Question).filter(Question.course_id == course.id).all()}

            for q_data in questions_data:
                q_hash = self._generate_question_hash(q_data)
                if q_hash in existing_question_hashes:
                    logger.info(f"Skipping duplicate question (hash: {q_hash}): {q_data['question_text'][:50]}...")
                    self.stats['skipped'] += 1
                    continue
                
                self._process_single_question(db, course, q_data)
            
            if not self.dry_run:
                db.commit()
            self._print_final_stats()

    def update_questions(self, course_name: str, json_file_path: str):
        """Updates existing questions based on content hash."""
        logger.info(f"Starting 'update' operation for course '{course_name}' from '{json_file_path}'")
        questions_data = self._load_json_data(json_file_path)
        if not questions_data: return

        with get_db() as db:
            course = db.query(Course).filter(Course.name == course_name).first()
            if not course:
                logger.error(f"Course '{course_name}' not found. Please create it first.")
                return

            existing_questions_map = {self._generate_question_hash(q.to_dict()): q for q in db.query(Question).filter(Question.course_id == course.id).all()}

            for q_data in questions_data:
                q_hash = self._generate_question_hash(q_data)
                if q_hash in existing_questions_map:
                    self._process_single_question(db, course, q_data, existing_question=existing_questions_map[q_hash])
                else:
                    logger.warning(f"Question with hash {q_hash} not found for update: {q_data['question_text'][:50]}...")
                    self.stats['skipped'] += 1 # Count as skipped for update operation
            
            if not self.dry_run:
                db.commit()
            self._print_final_stats()

    def replace_all_questions(self, course_name: str, json_file_path: str):
        """Deletes all existing questions for a course and loads new ones."""
        logger.info(f"Starting 'replace_all' operation for course '{course_name}' from '{json_file_path}'")
        questions_data = self._load_json_data(json_file_path)
        if not questions_data: return

        with get_db() as db:
            course = db.query(Course).filter(Course.name == course_name).first()
            if not course:
                logger.error(f"Course '{course_name}' not found. Please create it first.")
                return

            if not self.dry_run:
                # Delete all existing questions for this course
                num_deleted = db.query(Question).filter(Question.course_id == course.id).delete()
                db.commit()
                logger.info(f"Deleted {num_deleted} old questions for '{course_name}'.")
            else:
                logger.info(f"[DRY RUN] Would delete all existing questions for '{course_name}'.")

            for q_data in questions_data:
                self._process_single_question(db, course, q_data)
            
            if not self.dry_run:
                db.commit()
            self._print_final_stats()

    def _load_json_data(self, json_file_path: str) -> Optional[List[Dict[str, Any]]]:
        """Loads question data from a JSON file."""
        if not os.path.exists(json_file_path):
            logger.error(f"JSON file not found at: {json_file_path}")
            return None
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {json_file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while reading {json_file_path}: {e}")
            return None

    def _print_final_stats(self):
        stats = self.stats
        elapsed = time.time() - stats['start_time']
        logger.info(f"Operation Complete. Total processed: {stats['processed']}, Added: {stats['added']}, Updated: {stats['updated']}, Skipped: {stats['skipped']}.")
        logger.info(f"Rendering Stats: Rendered: {stats['rendered']}, Cached: {stats['cached_render']}, Failed: {stats['failed_render']}. Time: {elapsed:.1f}s.")

def main():
    print("DEBUG: main() function started.") # Added for debugging
    parser = argparse.ArgumentParser(description="Manage quiz questions in the database, including LaTeX rendering and S3 uploads.")
    parser.add_argument("--course-name", required=True, help="The name of the course to manage questions for.")
    parser.add_argument("--json-file", required=True, help="Path to the JSON file containing question data.")
    parser.add_argument("--operation", choices=['add', 'update', 'replace_all'], required=True,
                        help="Operation to perform: 'add' (new questions, skip duplicates), 'update' (existing questions by hash), 'replace_all' (delete all and add new).")
    parser.add_argument("--dry-run", action='store_true', help="Perform a dry run without making actual changes to the database or S3.")
    parser.add_argument("--force-render", action='store_true', help="Force re-rendering of LaTeX images, even if cached on S3.")
    args = parser.parse_args()

    manager = QuestionManager(dry_run=args.dry_run, force_render=args.force_render)

    if args.operation == 'add':
        manager.add_questions(args.course_name, args.json_file)
    elif args.operation == 'update':
        manager.update_questions(args.course_name, args.json_file) # Corrected typo here
    elif args.operation == 'replace_all':
        manager.replace_all_questions(args.course_name, args.json_file)

if __name__ == "__main__":
    print("DEBUG: Entering __main__ block.") # Added for debugging
    # Add a to_dict method to the Question model for hashing
    # This is a temporary patch for the script to work.
    # Ideally, this should be in the models.py file.
    def question_to_dict(self):
        return {
            "question_text": self.question_text,
            "options": self.options,
            "explanation": self.explanation,
            "has_latex": self.has_latex,
            "difficulty_score": self.difficulty_score
        }
    Question.to_dict = question_to_dict
    try:
        main()
    except Exception as e:
        logger.error(f"An unhandled error occurred: {e}")