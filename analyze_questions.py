import json
import argparse
from collections import defaultdict
import numpy as np

def analyze_questions(file_path):
    """
    Analyzes a JSON file of questions to provide key metrics.

    Args:
        file_path (str): The path to the JSON file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}")
        return

    total_questions = len(questions)
    missing_fields = defaultdict(int)
    has_latex_count = 0
    difficulty_scores = []
    invalid_correct_answer_index_count = 0

    for i, q in enumerate(questions):
        # Check for missing fields
        if 'question_text' not in q or not q['question_text']:
            missing_fields['question_text'] += 1
        if 'options' not in q or not isinstance(q['options'], list):
            missing_fields['options'] += 1
        if 'correct_answer_index' not in q:
            missing_fields['correct_answer_index'] += 1
        if 'explanation' not in q or not q['explanation']:
            missing_fields['explanation'] += 1
        if 'has_latex' not in q:
            missing_fields['has_latex'] += 1
        if 'difficulty_score' not in q:
            missing_fields['difficulty_score'] += 1

        # Validate correct_answer_index
        if 'options' in q and isinstance(q['options'], list) and 'correct_answer_index' in q:
            if not (0 <= q['correct_answer_index'] < len(q['options'])):
                invalid_correct_answer_index_count += 1

        # Track has_latex
        if q.get('has_latex') is True:
            has_latex_count += 1

        # Track difficulty_score
        if 'difficulty_score' in q and isinstance(q.get('difficulty_score'), (int, float)):
            difficulty_scores.append(q['difficulty_score'])

    # --- Print Summary ---
    print(f"\n--- Analysis Summary for {file_path} ---")
    print(f"Total Questions: {total_questions}")

    print("\n--- Field Presence ---")
    for field, count in missing_fields.items():
        print(f"Missing '{field}': {count} ({count/total_questions:.2%})")

    print("\n--- Content Analysis ---")
    print(f"Questions with LaTeX: {has_latex_count} ({has_latex_count/total_questions:.2%})")
    print(f"Invalid 'correct_answer_index': {invalid_correct_answer_index_count}")


    if difficulty_scores:
        print("\n--- Difficulty Score Analysis ---")
        print(f"  Min: {np.min(difficulty_scores):.2f}")
        print(f"  Max: {np.max(difficulty_scores):.2f}")
        print(f"  Average: {np.mean(difficulty_scores):.2f}")
        print(f"  Standard Deviation: {np.std(difficulty_scores):.2f}")
    else:
        print("\n--- Difficulty Score Analysis ---")
        print("  No valid difficulty scores found.")

    print("\n--- End of Report ---\
")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a JSON file with questions.")
    parser.add_argument("file_path", type=str, help="The path to the JSON file to analyze.")
    args = parser.parse_args()
    analyze_questions(args.file_path)