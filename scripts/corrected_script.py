#!/usr/bin/env python3
"""
Offline Pre-processing Script for LaTeX Question Rendering
"""
import os
import sys
import logging
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional
import tempfile
import subprocess
import shutil
import boto3
from botocore.exceptions import ClientError
import hashlib
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import get_db
from src.config import S3_BUCKET_NAME, AWS_REGION
from sqlalchemy import text
from sqlalchemy.orm import Session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('preprocessing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)



class RobustQuestionRenderer:
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=AWS_REGION)
        self.validate_environment()
        self.stats = {
            'processed': 0, 'rendered': 0, 'cached': 0, 'failed': 0, 'start_time': time.time()
        }

    def validate_environment(self):
        convert_exe = 'magick' if sys.platform == 'win32' else 'convert'
        required_tools = ['pdflatex', convert_exe]
        if not all(shutil.which(tool) for tool in required_tools):
            raise EnvironmentError(f"Missing required tools: {required_tools}. Install TeX Live and ImageMagick.")
        try:
            self.s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix='rendered-cache/', MaxKeys=1)
            logger.info("S3 connectivity and permissions verified successfully")
        except Exception as e:
            raise EnvironmentError(f"S3 connectivity failed: {e}")
        logger.info("Environment validation passed")

    def _sanitize_latex(self, text: str) -> str:
        if not text:
            return ""
        # More aggressive data cleaning: remove weird whitespace, then fix known typos
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('rac{', '\frac{').replace(' o ', ' \to ')
        return text

    def create_latex_document(self, question_text: str, options: List[str]) -> str:
        question_clean = self._sanitize_latex(question_text)
        options_clean = [self._sanitize_latex(opt) for opt in options]
        
        # Use a list to build the document parts to avoid string formatting issues
        doc_parts = [
            r'\documentclass[12pt,a4paper]{article}',
            r'\usepackage[utf8]{inputenc}',
            r'\usepackage[T1]{fontenc}',
            r'\usepackage{amsmath}',
            r'\usepackage{amsfonts}',
            r'\usepackage{amssymb}',
            r'\usepackage{geometry}',
            r'\geometry{paperwidth=210mm, paperheight=150mm, margin=15mm}',
            r'\pagestyle{empty}',
            r'\begin{document}',
            r'\begin{minipage}{0.9\textwidth}',
            rf'\large {question_clean}',
            r'\end{minipage}',
            r'\vspace{8mm}'
        ]

        option_letters = ['A', 'B', 'C', 'D', 'E']
        for i, option in enumerate(options_clean):
            doc_parts.append(rf'\noindent \textbf{{{option_letters[i]}}}) {option}')
            doc_parts.append(r'\vspace{2mm}')
            
        doc_parts.append(r'\end{document}')
        
        return '\n'.join(doc_parts)

    def render_and_upload(self, question_id: int, question_text: str, options: List[str]) -> Optional[str]:
        logger.info(f"Processing question {question_id}: {question_text[:50]}...")
        self.stats['processed'] += 1
        cache_key = hashlib.md5((question_text + "".join(options)).encode()).hexdigest()
        s3_key = f"rendered-cache/{cache_key}.png"
        try:
            self.s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"Question {question_id} already cached")
            self.stats['cached'] += 1
            return url
        except ClientError as e:
            if e.response['Error']['Code'] != '404': raise

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            tex_file = temp_path / "question.tex"
            latex_content = self.create_latex_document(question_text, options)
            with open(tex_file, 'w', encoding='utf-8') as f: f.write(latex_content)

            try:
                subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-output-directory', str(temp_path), str(tex_file)], check=True, capture_output=True, text=True, timeout=30)
                pdf_file = temp_path / "question.pdf"
                png_file = temp_path / "question.png"
                
                convert_exe = 'magick' if sys.platform == 'win32' else 'convert'
                convert_cmd = [convert_exe, '-density', '300', str(pdf_file), str(png_file)]
                
                subprocess.run(convert_cmd, check=True, capture_output=True, text=True, timeout=30)
                with open(png_file, 'rb') as f: png_data = f.read()
                self.s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=png_data, ContentType='image/png')
                url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
                logger.info(f"Successfully processed question {question_id}")
                self.stats['rendered'] += 1
                return url
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                error_message = f"Rendering failed for question {question_id}: {e}"
                if isinstance(e, subprocess.CalledProcessError):
                    # Adding detailed output from the failed process
                    error_message += f"\n--- PDFLATEX STDOUT ---\n{e.stdout}\n--- PDFLATEX STDERR ---\n{e.stderr}"
                logger.error(error_message)
                # Also log the tex file content for debugging
                logger.error(f"--- TEX CONTENT ---\n{latex_content}")
                self.stats['failed'] += 1
                return None

class QuestionPreprocessor:
    def __init__(self, batch_size: int = 10):
        self.renderer = RobustQuestionRenderer()
        self.batch_size = batch_size

    def get_questions_needing_rendering(self, session: Session, limit: Optional[int] = None) -> List[Dict]:
        # We now assume LaTeX is indicated by the presence of $ delimiters.
        query = text("SELECT id, question_text, options FROM questions 
                     WHERE (image_url IS NULL OR image_url = '') 
                     AND (question_text LIKE '%$%' OR options::text LIKE '%$%')
                     ORDER BY id")
        if limit:
            query = text(f"{query.text} LIMIT {limit}")
        
        result = session.execute(query)
        return [{"id": r.id, "question_text": r.question_text, "options": r.options} for r in result]

    def update_question_image_url(self, session: Session, question_id: int, image_url: str):
        try:
            update_query = text("UPDATE questions SET image_url = :image_url WHERE id = :question_id")
            session.execute(update_query, {'image_url': image_url, 'question_id': question_id})
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update question {question_id}: {e}")

    def process_questions(self, limit: Optional[int] = None, dry_run: bool = False):
        logger.info(f"Starting question preprocessing. Limit: {limit}, Dry run: {dry_run}")
        with get_db() as session:
            questions = self.get_questions_needing_rendering(session, limit)
            if not questions:
                logger.info("No questions need rendering!")
                return

            logger.info(f"Found {len(questions)} questions to process.")
            for question in questions:
                if dry_run:
                    logger.info(f"[DRY RUN] Would process question {question['id']}")
                    continue
                image_url = self.renderer.render_and_upload(question['id'], question['question_text'], question['options'])
                if image_url:
                    self.update_question_image_url(session, question['id'], image_url)
                if self.renderer.stats['processed'] % 10 == 0:
                    self.print_progress_stats()
            self.print_final_stats()

    def print_progress_stats(self):
        stats = self.renderer.stats
        logger.info(f"Progress: {stats['processed']} processed, {stats['rendered']} rendered, {stats['cached']} cached, {stats['failed']} failed.")

    def print_final_stats(self):
        stats = self.renderer.stats
        elapsed = time.time() - stats['start_time']
        logger.info(f"Preprocessing Complete. Total: {stats['processed']}, Rendered: {stats['rendered']}, Cached: {stats['cached']}, Failed: {stats['failed']}. Time: {elapsed:.1f}s.")

def main():
    parser = argparse.ArgumentParser(description="Preprocess LaTeX questions.")
    parser.add_argument("--limit", type=int, help="Limit number of questions to process.")
    parser.add_argument("--dry-run", action='store_true', help="Show what would be done.")
    args = parser.parse_args()
    preprocessor = QuestionPreprocessor()
    preprocessor.process_questions(limit=args.limit, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
