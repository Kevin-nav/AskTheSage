import json
import logging
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.services.rendering_service import MCQImageRenderer, MCQQuestion

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Set the number of questions you want to render from the file
NUMBER_TO_RENDER = 5

if __name__ == "__main__":
    renderer = MCQImageRenderer()
    
    json_file_path = Path("formatted_questions/calculus/calculus.json")
    course_name = "calculus"

    logger.info(f"Attempting to render the first {NUMBER_TO_RENDER} questions from {json_file_path}...")

    results = []
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            all_questions_data = json.load(f)
        
        questions_to_process = all_questions_data[:NUMBER_TO_RENDER]
        
        if not questions_to_process:
            logger.warning("No questions found in the JSON file.")
        
        total_to_process = len(questions_to_process)
        for i, question_data in enumerate(questions_to_process):
            try:
                logger.info(f"--- Processing question {i + 1}/{total_to_process} ---")
                
                # Log the question data for debugging
                logger.debug(f"Question text: {question_data.get('question_text', 'N/A')[:100]}...")
                logger.debug(f"Has LaTeX: {question_data.get('has_latex', False)}")
                
                question = MCQQuestion(
                    question_text=question_data['question_text'],
                    options=question_data['options'],
                    correct_answer_index=question_data['correct_answer_index'],
                    explanation=question_data['explanation'],
                    has_latex=question_data.get('has_latex', False),
                    course=course_name,
                    topic=question_data.get('topic', '')
                )
                
                question_file, explanation_file = renderer.render_question(question, i + 1)
                results.append((question.question_id, question_file, explanation_file))
                
                if question_file:
                    logger.info(f"Successfully rendered question {i + 1}")
                else:
                    logger.warning(f"Failed to render question {i + 1}")
                    
            except KeyError as e:
                logger.error(f"Skipping question {i+1} due to missing key: {e}")
                logger.error(f"Available keys: {list(question_data.keys())}")
            except Exception as e:
                logger.error(f"Error processing question {i+1}: {e}", exc_info=True)

    except FileNotFoundError:
        logger.error(f"JSON file not found: {json_file_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from file: {json_file_path}")
        logger.error(f"JSON error details: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)

    # Print results
    print("\n" + "="*60)
    print("Rendering Test Complete")
    print("="*60)
    
    if results:
        print(f"\n✓ Successfully processed {len(results)} question(s):\n")
        for idx, (question_id, q_file, e_file) in enumerate(results, 1):
            print(f"  {idx}. Question ID: {question_id}")
            print(f"     • Question Image: {q_file if q_file else 'Failed to render'}")
            if e_file:
                print(f"     • Explanation Image: {e_file}")
            print()
    else:
        print("\n✗ No questions were successfully rendered.")
        print("  Please check the logs above for specific errors.")
        print("\n  Common issues to check:")
        print("  • Is LaTeX (pdflatex) installed and in PATH?")
        print("  • Is poppler-utils (pdftocairo) installed?")
        print("  • Does the JSON file exist at the specified path?")
        print("  • Are the JSON questions properly formatted?")
    
    print("\n" + "="*60)