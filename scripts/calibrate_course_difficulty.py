# scripts/calibrate_course_difficulty.py

import sys
import os
from sqlalchemy import func

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db
from src.models.models import Course, Question

def calibrate_difficulty():
    """
    Calculates and updates the min and max difficulty scores for each course.
    """
    with get_db() as session:
        courses = session.query(Course).all()
        
        for course in courses:
            min_max_scores = session.query(
                func.min(Question.difficulty_score),
                func.max(Question.difficulty_score)
            ).filter(Question.course_id == course.id).one()
            
            min_difficulty, max_difficulty = min_max_scores
            
            if min_difficulty is not None and max_difficulty is not None:
                course.min_difficulty = min_difficulty
                course.max_difficulty = max_difficulty
                print(f"Updated course '{course.name}': Min={min_difficulty}, Max={max_difficulty}")
            else:
                print(f"Skipping course '{course.name}' - no questions with difficulty scores found.")
                
        session.commit()
        print("\nCourse difficulty calibration complete.")

if __name__ == "__main__":
    calibrate_difficulty()
