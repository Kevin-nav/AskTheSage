from sqlalchemy.orm import Session
from src.models.models import Faculty, Program, Level, Course

def get_all_faculties(db: Session):
    """Fetches all faculties from the database."""
    return db.query(Faculty).order_by(Faculty.name).all()

def get_programs_for_faculty(db: Session, faculty_id: int):
    """Fetches all programs for a given faculty."""
    return db.query(Program).filter(Program.faculty_id == faculty_id).order_by(Program.name).all()

def get_levels_for_program(db: Session, program_id: int):
    """Fetches all levels that have at least one course associated with the given program."""
    levels = db.query(Level).join(Course).filter(Course.programs.any(id=program_id)).distinct().order_by(Level.name).all()
    return levels

def get_courses_for_program_and_level(db: Session, program_id: int, level_id: int):
    """Fetches all courses for a given program and level."""
    courses = db.query(Course).filter(
        Course.level_id == level_id,
        Course.programs.any(id=program_id)
    ).order_by(Course.name).all()
    return courses