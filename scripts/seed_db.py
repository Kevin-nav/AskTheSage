import os
import sys
import logging
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import sessionmaker
from src.database import engine
from src.logging_config import setup_logging
from src.models.models import Faculty, Program, Level, Course

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_database():
    """
    Populates the database with initial data for faculties, programs, levels, and courses.
    """
    db = SessionLocal()

    try:
        # Data structure from user context
        faculty_data = {
            "Faculty of Computing and Mathematical Sciences": [
                "Cyber Security", "Statistical Data Science", "Information Systems and Technology",
                "Mathematics", "Computer Science and Engineering"
            ],
            "School of Petroleum": [
                "Natural Gas", "Chemical Engineering", "Petroleum Geoscience Engineering",
                "Petroleum Refinery and Petrochemical Engineering", "Petroleum Engineering"
            ],
            "Faculty of Integrated and Mathematical Science": [
                "Logistics and Transport Management", "Economics and Industrial Organization"
            ],
            "Faculty of Minerals and Minerals Technology": [
                "Minerals Engineering", "Mining Engineering"
            ],
            "Faculty of Geosciences and Environmental Studies": [
                "Environmental and Safety Engineering", "Geomatics Engineering",
                "Land Administration", "Geological Engineering"
            ],
            "Faculty of Engineering": [
                "Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"
            ]
        }

        course_data = {
            "Academic Writing": ["Cyber Security", "Information Systems and Technology", "Mathematics", "Computer Science and Engineering", "Natural Gas", "Chemical Engineering", "Petroleum Geoscience Engineering", "Petroleum Refinery and Petrochemical Engineering", "Petroleum Engineering", "Economics and Industrial Organization", "Minerals Engineering", "Mining Engineering", "Environmental and Safety Engineering", "Geomatics Engineering", "Land Administration", "Geological Engineering", "Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"],
            "Calculus": ["Cyber Security", "Information Systems and Technology", "Computer Science and Engineering", "Natural Gas", "Chemical Engineering", "Petroleum Geoscience Engineering", "Petroleum Refinery and Petrochemical Engineering", "Petroleum Engineering", "Minerals Engineering", "Mining Engineering", "Environmental and Safety Engineering", "Geomatics Engineering", "Geological Engineering", "Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"],
            "Strength Of Materials": ["Natural Gas", "Chemical Engineering", "Petroleum Geoscience Engineering", "Petroleum Refinery and Petrochemical Engineering", "Petroleum Engineering", "Minerals Engineering", "Mining Engineering", "Environmental and Safety Engineering", "Geomatics Engineering", "Geological Engineering", "Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"],
            "Basic French II": ["Statistical Data Science", "Cyber Security", "Mathematics", "Computer Science and Engineering", "Natural Gas", "Chemical Engineering", "Petroleum Geoscience Engineering", "Petroleum Refinery and Petrochemical Engineering", "Petroleum Engineering", "Economics and Industrial Organization", "Minerals Engineering", "Mining Engineering", "Environmental and Safety Engineering", "Geomatics Engineering", "Land Administration", "Geological Engineering", "Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"],
            "Engineering Drawing": ["Computer Science and Engineering", "Natural Gas", "Chemical Engineering", "Petroleum Geoscience Engineering", "Petroleum Refinery and Petrochemical Engineering", "Petroleum Engineering", "Minerals Engineering", "Mining Engineering", "Environmental and Safety Engineering", "Geomatics Engineering", "Geological Engineering", "Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"],
            "Basic Electronics": ["Computer Science and Engineering", "Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"],
            "Applied Electronics": ["Natural Gas", "Chemical Engineering", "Petroleum Geoscience Engineering", "Petroleum Refinery and Petrochemical Engineering", "Petroleum Engineering", "Minerals Engineering", "Environmental and Safety Engineering", "Geomatics Engineering"],
            "Basic Material Science": ["Mechanical Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"],
            "Instruments and Measurements": ["Electrical and Electronics Engineering"],
            "Analytical Chemistry": ["Chemical Engineering", "Petroleum Refinery and Petrochemical Engineering"],
            "Physical Chemistry": ["Chemical Engineering", "Petroleum Geoscience Engineering", "Petroleum Refinery and Petrochemical Engineering", "Minerals Engineering"],
            "Physical and Analytical Chemistry": ["Natural Gas", "Petroleum Geoscience Engineering", "Petroleum Engineering", "Mining Engineering", "Geological Engineering"],
            "Web Programming": ["Cyber Security", "Information Systems and Technology", "Computer Science and Engineering"],
            "Object Oriented Programming": ["Cyber Security", "Information Systems and Technology", "Computer Science and Engineering", "Renewable Energy Engineering", "Electrical and Electronics Engineering"]
        }

        # --- Create Level ---
        level_100 = db.query(Level).filter_by(name="Level 100").first() or Level(name="Level 100")
        db.add(level_100)

        # --- Create Faculties and Programs ---
        program_objects = {}
        for faculty_name, program_list in faculty_data.items():
            faculty = db.query(Faculty).filter_by(name=faculty_name).first() or Faculty(name=faculty_name)
            db.add(faculty)
            for prog_name in program_list:
                program = db.query(Program).filter_by(name=prog_name).first() or Program(name=prog_name, faculty=faculty)
                program_objects[prog_name] = program
                db.add(program)

        # --- Create Courses and Associations ---
        course_objects = {}
        for course_name, program_names in course_data.items():
            course = db.query(Course).filter_by(name=course_name).first() or Course(name=course_name, level=level_100)
            db.add(course)
            course_objects[course_name] = course
            
            for prog_name in program_names:
                program_obj = program_objects[prog_name]
                if program_obj not in course.programs:
                    course.programs.append(program_obj)

        db.commit()
        logger.info("\nDatabase seeding completed successfully!")

    except Exception as e:
        db.rollback()
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()