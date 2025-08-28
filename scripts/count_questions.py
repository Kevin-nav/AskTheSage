import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Add project root to path to allow imports from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import get_db
from src.models.models import Course, Question

def count_questions_for_course(course_name: str) -> int:
    with get_db() as db:
        course = db.query(Course).filter(Course.name == course_name).first()
        if not course:
            print(f"Error: Course '{course_name}' not found in the database.")
            return 0
        
        question_count = db.query(Question).filter(Question.course_id == course.id).count()
        return question_count

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/count_questions.py \"<Course Name>\"")
        sys.exit(1)
    
    course_name = sys.argv[1]
    count = count_questions_for_course(course_name)
    if count > 0:
        print(f"There are {count} questions for the course '{course_name}' in the database.")

