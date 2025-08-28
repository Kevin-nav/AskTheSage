import os
import subprocess
import tempfile
import hashlib
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple, List

import boto3
from dotenv import load_dotenv
from pdf2image import convert_from_path

# Add root directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db
from src.models.models import Question, Course

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

class LatexRendererS3:
    """Renders LaTeX questions and uploads them to S3."""

    def __init__(self, bucket_name: str, region: str):
        if not all([bucket_name, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, region]):
            raise ValueError("Missing one or more required S3 environment variables.")
        self.bucket_name = bucket_name
        self.aws_region = region
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=region
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.question_template = self._load_template("question")
        self.explanation_template = self._load_template("explanation")

    def _load_template(self, template_type: str) -> str:
        # Using standalone class to auto-crop whitespace. Increased font to 16pt.
        if template_type == "question":
            return r"""\documentclass[16pt, border=10pt]{standalone}
\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}\usepackage{amsmath}\usepackage{amsfonts}
\usepackage{amssymb}\usepackage{mhchem}\usepackage{enumitem}\usepackage{xcolor}
\usepackage{textgreek}\DeclareUnicodeCharacter{2081}{\textsubscript{1}}\DeclareUnicodeCharacter{2082}{\textsubscript{2}}
\usepackage[most]{tcolorbox}\usepackage{varwidth}
\definecolor{questionbg}{rgb}{0.95, 0.95, 0.98}


\begin{document}
\begin{varwidth}{0.9\textwidth}
\begin{tcolorbox}[colback=questionbg, colframe=black!50!blue, title=Question]
{QUESTION_TEXT}
\end{tcolorbox}
\vspace{0.3cm}
\textbf{Options:}
\begin{enumerate}[label=\textbf{\Alph*})]
{OPTIONS}
\end{enumerate}
\end{varwidth}
\end{document}"""
        else:
            return r"""\documentclass[16pt, border=10pt]{standalone}
\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}\usepackage{amsmath}\usepackage{amsfonts}
\usepackage{amssymb}\usepackage{mhchem}\usepackage{xcolor}
\usepackage{textgreek}\DeclareUnicodeCharacter{2081}{\textsubscript{1}}\DeclareUnicodeCharacter{2082}{\textsubscript{2}}
\usepackage[most]{tcolorbox}\usepackage{varwidth}
\definecolor{explainbg}{rgb}{0.95, 0.98, 0.95}\definecolor{answerbg}{rgb}{0.98, 0.95, 0.95}
\begin{document}
\begin{varwidth}{0.9\textwidth}
\begin{tcolorbox}[colback=answerbg, colframe=green!50!black, title=Answer: {CORRECT_ANSWER}]
\textbf{Correct Answer:} {CORRECT_OPTION}
\end{tcolorbox}
\vspace{0.3cm}
\begin{tcolorbox}[colback=explainbg, colframe=blue!50!black, title=Explanation]
{EXPLANATION_TEXT}
\end{tcolorbox}
\end{varwidth}
\end{document}"""

    def _clean_latex_text(self, text: str) -> str:
        if not text: return ""
        replacements = {"&": r" \& ", "%": r" \% ", "#": r" \# ", "_": r" \_ "}
        for char, escaped in replacements.items():
            text = text.replace(char, escaped)
        return text

    def _render_to_pdf(self, latex_content: str, output_path: str) -> bool:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                tex_file = Path(temp_dir) / "render.tex"
                tex_file.write_text(latex_content, encoding='utf-8')
                result = subprocess.run(
                    ['pdflatex', '-interaction=nonstopmode', '-output-directory', temp_dir, str(tex_file)],
                    capture_output=True, text=True, cwd=temp_dir
                )
                if result.returncode != 0:
                    log_path = Path(temp_dir) / "render.log"
                    logger.error(f"LaTeX failed. Log:\n{log_path.read_text(encoding='utf-8')}")
                    return False
                pdf_file = Path(temp_dir) / "render.pdf"
                if pdf_file.exists():
                    pdf_file.rename(output_path)
                    return True
                return False
        except Exception as e:
            logger.error(f"Error during PDF rendering: {e}", exc_info=True)
            return False

    def _pdf_to_image(self, pdf_path: str, image_path: str) -> bool:
        try:
            images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=1)
            if images:
                images[0].save(image_path, 'PNG')
                # Log the file size
                try:
                    file_size = os.path.getsize(image_path)
                    logger.info(f"Generated image: {image_path} (Size: {file_size / 1024:.2f} KB)")
                except OSError as e:
                    logger.error(f"Could not get file size for {image_path}: {e}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error converting PDF to image: {e}", exc_info=True)
            return False

    def _upload_to_s3(self, local_path: str, s3_key: str) -> Optional[str]:
        try:
            self.s3_client.upload_file(local_path, self.bucket_name, s3_key, ExtraArgs={'ContentType': 'image/png'})
            url = f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{s3_key}"
            logger.info(f"Successfully uploaded to {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {e}", exc_info=True)
            return None

    def render_and_upload(self, question: Question) -> Tuple[Optional[str], Optional[str]]:
        content_str = f"{question.question_text}{question.explanation}{question.id}"
        q_hash = hashlib.md5(content_str.encode()).hexdigest()[:12]
        course_name_slug = question.course.name.lower().replace(' ', '_')
        
        q_filename = f"{course_name_slug}_{q_hash}_q.png"
        e_filename = f"{course_name_slug}_{q_hash}_e.png"
        s3_q_key = f"rendered-cache/{q_filename}"
        s3_e_key = f"rendered-cache/{e_filename}"

        # --- Render Question ---
        q_url = None
        options_latex = "".join([f"\item {self._clean_latex_text(opt)}\n" for opt in question.options.values()])
        q_latex = self.question_template.replace("{QUESTION_TEXT}", self._clean_latex_text(question.question_text))
        q_latex = q_latex.replace("{OPTIONS}", options_latex)
        
        temp_pdf_path = Path(self.temp_dir.name) / f"{q_hash}_q.pdf"
        temp_img_path = Path(self.temp_dir.name) / q_filename

        if self._render_to_pdf(q_latex, str(temp_pdf_path)):
            if self._pdf_to_image(str(temp_pdf_path), str(temp_img_path)):
                q_url = self._upload_to_s3(str(temp_img_path), s3_q_key)
        
        # --- Render Explanation ---
        e_url = None
        if question.explanation:
            correct_letter = chr(65 + question.correct_answer)
            correct_option = list(question.options.values())[question.correct_answer]
            e_latex = self.explanation_template.replace("{CORRECT_ANSWER}", correct_letter)
            e_latex = e_latex.replace("{CORRECT_OPTION}", self._clean_latex_text(correct_option))
            e_latex = e_latex.replace("{EXPLANATION_TEXT}", self._clean_latex_text(question.explanation))
            
            temp_pdf_path = Path(self.temp_dir.name) / f"{q_hash}_e.pdf"
            temp_img_path = Path(self.temp_dir.name) / e_filename

            if self._render_to_pdf(e_latex, str(temp_pdf_path)):
                if self._pdf_to_image(str(temp_pdf_path), str(temp_img_path)):
                    e_url = self._upload_to_s3(str(temp_img_path), s3_e_key)

        return q_url, e_url

    def __del__(self):
        self.temp_dir.cleanup()

def process_questions_in_db(force_rerun: bool, id_list: Optional[List[int]]):
    """Main function to process questions from the database."""
    try:
        renderer = LatexRendererS3(bucket_name=S3_BUCKET_NAME, region=AWS_REGION)
    except ValueError as e:
        logger.error(f"Initialization failed: {e}")
        return

    with get_db() as db:
        query = db.query(Question).filter(Question.has_latex == True)

        if id_list:
            logger.info(f"Processing specific question IDs: {id_list}")
            query = query.filter(Question.id.in_(id_list))
        elif not force_rerun:
            logger.info("Processing questions that have not been rendered yet.")
            query = query.filter(Question.image_url == None)
        else:
            logger.warning("Forcing re-rendering of all LaTeX questions.")

        questions_to_render = query.join(Course).all()

        if not questions_to_render:
            logger.info("No questions found matching the criteria.")
            return

        logger.info(f"Found {len(questions_to_render)} questions to process.")
        total_processed = 0
        for question in questions_to_render:
            logger.info(f"Processing question ID: {question.id}...")
            try:
                q_url, e_url = renderer.render_and_upload(question)
                if q_url:
                    question.image_url = q_url
                    question.explanation_image_url = e_url  # Can be None
                    db.commit() # Commit after each successful question
                    logger.info(f"Successfully processed and committed question ID: {question.id}")
                    total_processed += 1
                else:
                    logger.error(f"Failed to render or upload question ID: {question.id}. Rolling back session for this question.")
                    db.rollback()
            except Exception as e:
                logger.error(f"An unexpected error occurred processing question ID {question.id}: {e}", exc_info=True)
                db.rollback()

        logger.info(f"--- Run Complete ---")
        logger.info(f"Successfully processed and updated {total_processed} questions in total.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render LaTeX questions and upload them to S3.")
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force re-rendering of all LaTeX questions, even if they already have an image URL."
    )
    parser.add_argument(
        '--ids',
        type=str,
        help="A comma-separated list of specific question IDs to process."
    )
    args = parser.parse_args()

    id_list = None
    if args.ids:
        try:
            id_list = [int(item.strip()) for item in args.ids.split(',')]
        except ValueError:
            logger.error("Invalid format for --ids. Please provide a comma-separated list of numbers.")
            sys.exit(1)

    process_questions_in_db(force_rerun=args.force, id_list=id_list)
