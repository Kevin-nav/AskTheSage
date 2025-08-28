import json
import os

def count_latex_questions(json_file_path: str) -> int:
    """
    Counts the number of questions with 'has_latex' set to true in a JSON file.
    """
    latex_question_count = 0
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for question in data:
                if question.get('has_latex') is True:
                    latex_question_count += 1
        else:
            # Handle case where JSON might contain a single question object
            if data.get('has_latex') is True:
                latex_question_count = 1
                
    except FileNotFoundError:
        print(f"Error: File not found at {json_file_path}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
    return latex_question_count

if __name__ == "__main__":
    json_file = "formatted_questions/basic_electronics_parts/basic_electronics_questions.json"
    count = count_latex_questions(json_file)
    print(f"Number of questions from {json_file} requiring LaTeX rendering: {count}")
