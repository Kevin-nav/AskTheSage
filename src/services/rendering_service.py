# rendering_service.py

import os
import hashlib
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import logging
import subprocess
import tempfile
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pdf2image import convert_from_path
import json

from src.config import S3_BUCKET_NAME, AWS_REGION

logger = logging.getLogger(__name__)

@dataclass
class MCQQuestion:
    """Data class for MCQ questions"""
    question_text: str
    options: List[str]
    correct_answer_index: int
    explanation: str
    has_latex: bool
    course: str = "default"
    topic: str = ""
    question_id: str = None

    def __post_init__(self):
        if not self.question_id:
            # Generate unique ID based on content
            content = f"{self.question_text}{self.options}{self.explanation}"
            self.question_id = hashlib.md5(content.encode()).hexdigest()[:12]

class MCQImageRenderer:
    """Main renderer class for MCQ questions"""
    
    def __init__(self, output_dir: str = "rendered_questions", db_path: str = "question_tracker.db"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.db_path = db_path
        self.init_database()
        
        # --- MODIFICATION START ---
        # A single, definitive header for all LaTeX documents
        self.latex_header = r"""
\documentclass[16pt, border=10pt]{standalone}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{amssymb}
\usepackage{mhchem}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage[most]{tcolorbox}
\usepackage{varwidth}
\usepackage{listings}
\usepackage{textcomp}
\usepackage{newunicodechar}
% Math Symbols
\newunicodechar{∫}{\ensuremath{\int}}
\newunicodechar{√}{\ensuremath{\sqrt}}
\newunicodechar{≠}{\ensuremath{\neq}}
\newunicodechar{≤}{\ensuremath{\leq}}
\newunicodechar{≥}{\ensuremath{\geq}}
\newunicodechar{×}{\ensuremath{\times}}
\newunicodechar{÷}{\ensuremath{\div}}
\newunicodechar{π}{\ensuremath{\pi}}
\newunicodechar{θ}{\ensuremath{\theta}}
% Superscripts
\newunicodechar{⁰}{\ensuremath{^0}}
\newunicodechar{¹}{\ensuremath{^1}}
\newunicodechar{²}{\ensuremath{^2}}
\newunicodechar{³}{\ensuremath{^3}}
\newunicodechar{⁴}{\ensuremath{^4}}
\newunicodechar{⁵}{\ensuremath{^5}}
\newunicodechar{⁶}{\ensuremath{^6}}
\newunicodechar{⁷}{\ensuremath{^7}}
\newunicodechar{⁸}{\ensuremath{^8}}
\newunicodechar{⁹}{\ensuremath{^9}}

% Configure listings package for better code rendering
\lstset{
    basicstyle=\small\ttfamily,
    breaklines=true,
    breakatwhitespace=false,
    showspaces=false,
    showstringspaces=false,
    showtabs=false,
    frame=single,
    rulecolor=\color{black!30},
    backgroundcolor=\color{gray!10},
    keywordstyle=\color{blue}\bfseries,
    commentstyle=\color{green!60!black},
    stringstyle=\color{red},
    numberstyle=\tiny\color{gray},
    captionpos=b,
    aboveskip=10pt,
    belowskip=10pt
}
"""
        
        # Template for the question body ONLY
        self.question_template_body = r"""
\definecolor{questionbg}{rgb}{0.95, 0.95, 0.98}
\begin{document}
\begin{varwidth}{0.9\textwidth}
\begin{tcolorbox}[colback=questionbg, colframe=black!50!blue, title=Question {QUESTION_NUMBER}]
{QUESTION_TEXT}
\end{tcolorbox}
\vspace{0.3cm}
\textbf{Options:}\\
{OPTIONS}
\end{varwidth}
\end{document}
"""

        # Template for the explanation body ONLY
        self.explanation_template_body = r"""
\definecolor{explainbg}{rgb}{0.95, 0.98, 0.95}
\definecolor{answerbg}{rgb}{0.98, 0.95, 0.95}
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
\end{document}
"""
        # --- MODIFICATION END ---

    def init_database(self):
        """Initialize SQLite database for tracking questions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                question_id TEXT PRIMARY KEY, course TEXT, topic TEXT,
                question_file TEXT, explanation_file TEXT, has_latex BOOLEAN,
                created_at TIMESTAMP, status TEXT DEFAULT 'rendered'
            )
        """
        )
        conn.commit()
        conn.close()

    # --- MODIFICATION START ---
    # Helper function to build the full LaTeX document
    def _build_latex_document(self, body_template: str, replacements: Dict[str, str]) -> str:
        """Combines the header and body, and performs text replacements."""
        content = body_template
        for key, value in replacements.items():
            content = content.replace(key, value)
        return self.latex_header + content
    # --- MODIFICATION END ---

    def clean_latex_text(self, text: str) -> str:
        """
        Cleans and prepares text for LaTeX by isolating math and code blocks,
        escaping the remaining plain text, and then reassembling the string with
        the correct LaTeX wrappers.
        """
        if not text:
            return ""


        # --- MODIFICATION START ---
        # Pre-process malformed square roots before other cleaning.
        text = re.sub(r'√\((.*?)\)', r'\\sqrt{\1}', text) # Handles formats like √(...)
        text = re.sub(r'√(\d+\.?\d*)', r'\\sqrt{\1}', text) # Handles formats like √45
        text = re.sub(r'√(\w+)', r'\\sqrt{\1}', text) # Handles single variables
        # --- MODIFICATION END ---

        # Use safe placeholders
        math_placeholder = "MATHBLOCKPLACEHOLDER{}"
        inline_code_placeholder = "INLINECODEPLACEHOLDER{}"
        multiline_code_placeholder = "MULTILINECODEPLACEHOLDER{}"

        # Storage for different content types
        math_blocks = []
        inline_code_blocks = []
        multiline_code_blocks = []

        # 1. Extract LaTeX math environments ($...$) to protect them
        def extract_math(match):
            math_blocks.append(match.group(0))
            return math_placeholder.format(len(math_blocks) - 1)
        
        text = re.sub(r'\$(?:\\.|[^$])*\$', extract_math, text)

        # 2. Extract multiline code blocks
        def extract_multiline_code(match):
            lang = match.group(1) or "text"
            code = match.group(2).strip()
            multiline_code_blocks.append((lang, code))
            return multiline_code_placeholder.format(len(multiline_code_blocks) - 1)
        text = re.sub(r'```(\w*)\n(.*?)\n```', extract_multiline_code, text, flags=re.DOTALL)

        # 3. Extract inline code blocks
        def extract_inline_code(match):
            code = match.group(1)
            inline_code_blocks.append(code)
            return inline_code_placeholder.format(len(inline_code_blocks) - 1)
        text = re.sub(r'`([^`]+)`', extract_inline_code, text)

        # 4. Escape LaTeX special characters in the remaining plain text
        replacements = [
            ('\\', r'\textbackslash{}'), ('&', r'\&'), ('%', r'\%'),
            ('#', r'\#'), ('_', r'\_'), ('{', r'\{'), ('}', r'\}'),
            ('~', r'\textasciitilde{}'), ('^', r'\textasciicircum{}'),
        ]
        
        for old, new in replacements:
            text = text.replace(old, new)
        
        # 5. Handle newlines for paragraph breaks
        text = text.replace('\n\n', '\\par\n')
        text = text.replace('\n', '\\newline\n')

        # 6. Restore the isolated blocks
        for i, (lang, code) in enumerate(multiline_code_blocks):
            lang_option = f"[language={lang}]" if lang and lang != "text" else ""
            replacement = f"\\begin{{lstlisting}}{lang_option}\n{code}\n\\end{{lstlisting}}"
            text = text.replace(multiline_code_placeholder.format(i), replacement)

        for i, code in enumerate(inline_code_blocks):
            escaped_inline_code = code
            for old, new in replacements:
                escaped_inline_code = escaped_inline_code.replace(old, new)
            replacement = f"\\texttt{{{escaped_inline_code}}}"
            text = text.replace(inline_code_placeholder.format(i), replacement)
            
        for i, math in enumerate(math_blocks):
            text = text.replace(math_placeholder.format(i), math)

        return text

    def render_to_pdf(self, latex_content: str, output_path: str) -> bool:
        """Render LaTeX content to PDF"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                tex_file = os.path.join(temp_dir, "question.tex")
                with open(tex_file, 'w', encoding='utf-8') as f:
                    f.write(latex_content)
                
                result = subprocess.run([
                    'pdflatex', '-interaction=nonstopmode',
                    '-output-directory', temp_dir, tex_file
                ], capture_output=True, text=True, cwd=temp_dir, encoding='utf-8', errors='ignore')
                
                if result.returncode != 0:
                    log_output = result.stdout or ""
                    logger.error(f"LaTeX compilation failed. Log:\n{log_output[-2000:]}")
                    return False
                
                pdf_file = os.path.join(temp_dir, "question.pdf")
                if os.path.exists(pdf_file):
                    os.rename(pdf_file, output_path)
                    return True
                else:
                    logger.error("PDF file not generated after successful compilation.")
                    return False
        except Exception as e:
            logger.error(f"Error during PDF rendering process: {e}")
            return False

    def pdf_to_image(self, pdf_path: str, image_path: str, dpi: int = 300) -> bool:
        """Convert PDF to high-quality PNG image"""
        try:
            images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=1)
            if images:
                images[0].save(image_path, 'PNG')
                return True
            return False
        except Exception as e:
            logger.error(f"Error converting PDF to image: {e}")
            return False

    def create_fallback_image(self, question: MCQQuestion, output_path: str) -> bool:
        """Create fallback text-based image using matplotlib"""
        try:
            import matplotlib.pyplot as plt
            import textwrap
            
            fig, ax = plt.subplots(figsize=(12, 9))
            fig.patch.set_facecolor('white')
            ax.axis('off')
            
            ax.text(0.5, 0.95, "Question (Fallback Rendering)", transform=ax.transAxes,
                   ha='center', va='center', fontsize=20, weight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='lightblue'))
            
            wrapped_question = textwrap.fill(question.question_text, 70)
            ax.text(0.05, 0.85, wrapped_question, transform=ax.transAxes, ha='left', va='top', fontsize=16,
                   wrap=True, bbox=dict(boxstyle="round,pad=0.3", facecolor='#f0f0f0'))
            
            y_pos = 0.70
            for i, option in enumerate(question.options):
                letter = chr(65 + i)
                wrapped_option = textwrap.fill(f"{letter}) {option}", 65)
                bg_color = 'lightgreen' if i == question.correct_answer_index else 'white'
                ax.text(0.05, y_pos, wrapped_option, transform=ax.transAxes, ha='left', va='top', fontsize=15,
                       bbox=dict(boxstyle="round,pad=0.2", facecolor=bg_color))
                y_pos -= 0.15
            
            plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.5, facecolor='white')
            plt.close()
            return True
        except Exception as e:
            logger.error(f"Error creating fallback image: {e}")
            return False

    def render_question(self, question: MCQQuestion, question_number: int = 1) -> Tuple[Optional[str], Optional[str]]:
        """Render a single question and its explanation to images"""
        question_filename = f"{question.course}_{question.question_id}_q.png"
        explanation_filename = f"{question.course}_{question.question_id}_e.png"
        question_path = self.output_dir / question_filename
        explanation_path = self.output_dir / explanation_filename
        
        question_success = False
        if question.has_latex:
            options_list = [
                f"\\textbf{{{chr(65 + i)}}}) {self.clean_latex_text(opt)}"
                for i, opt in enumerate(question.options)
            ]
            options_latex = r" \\ ".join(options_list)

            # Build the question document using the new helper
            question_replacements = {
                "{QUESTION_NUMBER}": str(question_number),
                "{QUESTION_TEXT}": self.clean_latex_text(question.question_text),
                "{OPTIONS}": options_latex
            }
            latex_content = self._build_latex_document(self.question_template_body, question_replacements)
            
            pdf_path = question_path.with_suffix('.pdf')
            if self.render_to_pdf(latex_content, str(pdf_path)):
                question_success = self.pdf_to_image(str(pdf_path), str(question_path))
                if pdf_path.exists(): os.remove(pdf_path)
        
        if not question_success:
            if question.has_latex:
                logger.warning(f"LaTeX rendering failed for question {question.question_id}, using fallback.")
            question_success = self.create_fallback_image(question, str(question_path))
        
        explanation_success = False
        if question.has_latex and question.explanation:
            correct_letter = chr(65 + question.correct_answer_index)
            correct_option = question.options[question.correct_answer_index]
            
            # Build the explanation document using the new helper
            explanation_replacements = {
                "{CORRECT_ANSWER}": correct_letter,
                "{CORRECT_OPTION}": self.clean_latex_text(correct_option),
                "{EXPLANATION_TEXT}": self.clean_latex_text(question.explanation)
            }
            latex_content = self._build_latex_document(self.explanation_template_body, explanation_replacements)
            
            pdf_path = explanation_path.with_suffix('.pdf')
            if self.render_to_pdf(latex_content, str(pdf_path)):
                explanation_success = self.pdf_to_image(str(pdf_path), str(explanation_path))
                if pdf_path.exists(): os.remove(pdf_path)
        
        self.update_database(question, 
                           question_filename if question_success else None,
                           explanation_filename if explanation_success else None)
        
        return (str(question_path) if question_success else None,
                str(explanation_path) if explanation_success else None)

    def update_database(self, question: MCQQuestion, question_file: Optional[str], explanation_file: Optional[str]):
        """Update database with rendered question info"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO questions (
                question_id, course, topic, question_file, 
                explanation_file, has_latex, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (question.question_id, question.course, question.topic, 
              os.path.basename(question_file) if question_file else None, 
              os.path.basename(explanation_file) if explanation_file else None, 
              question.has_latex, datetime.now(), 'rendered'))
        conn.commit()
        conn.close()

    def process_json_file(self, json_file: str, course_name: str) -> List[Tuple[str, Optional[str], Optional[str]]]:
        """Process a JSON file containing multiple questions"""
        results = []
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for i, question_data in enumerate(data):
                try:
                    question = MCQQuestion(
                        question_text=question_data['question_text'], 
                        options=question_data['options'],
                        correct_answer_index=question_data['correct_answer_index'],
                        explanation=question_data['explanation'], 
                        has_latex=question_data.get('has_latex', False),
                        course=course_name, 
                        topic=question_data.get('topic', '')
                    )
                    
                    question_file, explanation_file = self.render_question(question, i + 1)
                    results.append((question.question_id, question_file, explanation_file))
                    logger.info(f"Processed question {i + 1}/{len(data)}: {question.question_id}")
                except KeyError as e:
                    logger.error(f"Skipping question {i+1} due to missing key: {e}")
            return results
        except FileNotFoundError:
            logger.error(f"JSON file not found: {json_file}")
            return []
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from file: {json_file}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing {json_file}: {e}")
            return []

    def get_question_files(self, course: str = None, question_id: str = None) -> List[Dict]:
        """Retrieve question files from database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM questions WHERE 1=1"
        params = []
        if course:
            query += " AND course = ?"
            params.append(course)
        if question_id:
            query += " AND question_id = ?"
            params.append(question_id)
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

class LaTeXRenderingService:
    def __init__(self):
        self.s3_client = boto3.client('s3', region_name=AWS_REGION)
        self.latex_available = self._validate_latex_installation()
        if not self.latex_available:
            logger.error("LaTeX or pdftocairo is not installed. Rendering will fail.")
            logger.error("Please install a LaTeX distribution (like MiKTeX, TeX Live) and poppler-utils.")
        
        self.mcq_image_renderer = MCQImageRenderer()

    def _validate_latex_installation(self):
        """Check if pdflatex and pdftocairo are available"""
        try:
            subprocess.run(['pdflatex', '-version'], capture_output=True, text=True, check=True)
            subprocess.run(['pdftocairo', '-v'], capture_output=True, text=True, check=True)
            logger.info("LaTeX and pdf2image rendering environment validated successfully.")
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _generate_cache_key(self, content: str) -> str:
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _check_s3_cache(self, cache_key: str) -> str | None:
        try:
            s3_key = f"rendered-cache/{cache_key}.png"
            self.s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"Cache hit for key: {cache_key}")
            return url
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"Cache miss for key: {cache_key}")
            else:
                logger.error(f"S3 cache check failed: {e}")
            return None

    def _upload_to_s3_cache(self, cache_key: str, image_data: bytes) -> str | None:
        try:
            s3_key = f"rendered-cache/{cache_key}.png"
            self.s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=image_data, ContentType='image/png')
            url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"Uploaded to cache with key: {cache_key}")
            return url
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return None