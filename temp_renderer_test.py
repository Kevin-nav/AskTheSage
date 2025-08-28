import json
import os
import json
import logging
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.services.rendering_service import MCQImageRenderer, MCQQuestion

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example usage and testing
if __name__ == "__main__":
    renderer = MCQImageRenderer()
    
    dummy_questions = [
        {
            "question_text": r"What is the value of the integral $\int_0^1 x^2 dx$?",
            "options": [r"$\frac{1}{3}$", r"$\frac{1}{2}$", "1", "0"],
            "correct_answer_index": 0,
            "explanation": r"The integral of $x^2$ is $\frac{x^3}{3}$. Evaluating from 0 to 1 gives $\frac{1^3}{3} - \frac{0^3}{3} = \frac{1}{3}$.",
            "has_latex": True, "topic": "Calculus"
        },
        {
            "question_text": "Which of these is a logic gate? Note: this_is_a_test.",
            "options": ["AND", "IF", "WHILE", "FOR"],
            "correct_answer_index": 0,
            "explanation": "AND, OR, and NOT are fundamental logic gates. The underscore in 'this_is_a_test' should be escaped.",
            "has_latex": True, "topic": "Digital Logic"
        },
        {
            "question_text": "What is the output of the following Python code?\n```python\nx = 5\ny = 10\nprint(f'The sum is {x + y}')\n```",
            "options": ["The sum is 15", "15", "Error", "None of the above"],
            "correct_answer_index": 0,
            "explanation": "The code uses an f-string to print the sum of `x` and `y`, which is 15.",
            "has_latex": True, "topic": "Python"
        }
    ]
    
    os.makedirs("formatted_questions", exist_ok=True)
    json_file_path = "formatted_questions/basic_electronics_structured.json"
    with open(json_file_path, "w") as f:
        json.dump(dummy_questions, f, indent=4)

    results = renderer.process_json_file(json_file_path, "basic_electronics")
    
    print(f"\nProcessed {len(results)} questions.")
    for question_id, q_file, e_file in results:
        print(f"Question ID: {question_id}")
        print(f"  Question file: {q_file}")
        print(f"  Explanation file: {e_file}")
        print()
