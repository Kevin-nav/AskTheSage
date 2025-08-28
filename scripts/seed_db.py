import os
import sys
from dotenv import load_dotenv
import logging
from src.logging_config import setup_logging

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

from src.database import SessionLocal
from src.models.models import Faculty, Program, Level, Course

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

        # --- Add Sample Questions ---
#        sample_questions = {
#            "Web Programming": [
#                {"question_text": "Which HTML tag is used for creating an unordered list?", "options": ["<ol>", "<ul>", "<li>", "<dl>"], "correct_answer": "<ul>", "explanation": "The <ul> tag defines an unordered (bulleted) list."}, 
#                {"question_text": "What does CSS stand for?", "options": ["Cascading Style Sheets", "Creative Style Sheets", "Computer Style Sheets", "Colorful Style Sheets"], "correct_answer": "Cascading Style Sheets", "explanation": "CSS is used to style the visual presentation of a web page."},
#                {"question_text": "Which property is used to change the background color?", "options": ["color", "bgcolor", "background-color", "background"], "correct_answer": "background-color", "explanation": "The `background-color` property in CSS is used to set the background color of an element."}, 
#                {"question_text": "What is the correct HTML for referring to an external style sheet?", "options": ['<stylesheet>mystyle.css</stylesheet>', '<style src="mystyle.css">', '<link rel="stylesheet" type="text/css" href="mystyle.css">'], "correct_answer": "<link rel=\"stylesheet\" type=\"text/css\" href=\"mystyle.css\">
#", "explanation": "The <link> tag is used to link to external style sheets."} 
#            ],
#            "Calculus": [
#                {"question_text": "What is the derivative of $x^2$ ?", "options": ["$2x$", "$x$", "$x^3$", "$2$"], "correct_answer": "$2x$", "explanation": "Using the power rule, the derivative of $x^n$ is $nx^{n-1}$. So for $x^2$, it is $2x^{1} = 2x$"},
#                {"question_text": "What is the integral of $2x$ ?", "options": ["$x^2 + C$", "$2x^2 + C$", "$x + C$", "$2 + C$"], "correct_answer": "$x^2 + C$", "explanation": "The integral of $2x$ is $x^2$, and we add a constant of integration, C.
#"},
#                {"question_text": "What is the limit of $f(x) = frac{1}{x}$ as $x to infty$ ?", "options": ["0", "1", "infty", "-1"], "correct_answer": "0", "explanation": "As x gets infinitely large, 1/x approaches 0."
#            }
#            ],
#            "Strength Of Materials": [
#                {"question_text": "What is the formula for stress?", "options": ["Force / Area", "Mass * Acceleration", "Force * Distance", "Area / Force"], "correct_answer": "Force / Area", "explanation": "Stress is defined as the force per unit area."
#                },
#                {"question_text": "What does the Young's Modulus represent?", "options": ["Stiffness", "Ductility", "Strength", "Toughness"], "correct_answer": "Stiffness", "explanation": "Young's Modulus is a measure of the stiffness of a material."
#                }              {"question_text": "A ductile material is one that can be...", "options": ["easily shattered", "drawn into a wire", "magnetized", "heated to a high temperature"], "correct_answer": "drawn into a wire", "explanation": "Ductility is the ability of a material to be drawn into a wire."
#            }
#            ],
#            "Basic Electronics": [
#                {"question_text": "What is the unit of electrical resistance?", "options": ["Ohm", "Volt", "Ampere", "Watt"], "correct_answer": "Ohm", "explanation": "The Ohm is the SI unit of electrical resistance."
#                },
#                {"question_text": "What does LED stand for?", "options": ["Light Emitting Diode", "Low Energy Display", "Light Emitting Display", "Light Energy Diode"], "correct_answer": "Light Emitting Diode", "explanation": "LEDs are semiconductor devices that emit light when current flows through them."
#                },
#                {"question_text": "What type of current does a battery produce?", "options": ["Alternating Current (AC)", "Direct Current (DC)", "Pulsating Current", "Variable Current"], "correct_answer": "Direct Current (DC)", "explanation": "Batteries provide a constant flow of current in one direction, which is Direct Current (DC)."
#            }
#            ],
#            "Analytical Chemistry": [
#                {"question_text": "Balance the equation: $CH_4 + O_2 to CO_2 + H_2O$", "options": ["$CH_4 + 2O_2 to CO_2 + 2H_2O$", "$2CH_4 + O_2 to 2CO_2 + H_2O$", "$CH_4 + O_2 to CO_2 + H_2O$", "$CH_4 + 3O_2 to CO_2 + 2H_2O$"], "correct_answer": "$CH_4 + 2O_2 to CO_2 + 2H_2O$", "explanation": "To balance the equation, you need 2 oxygen molecules to react with 1 methane molecule to produce 1 carbon dioxide molecule and 2 water molecules."
#A                },
#                {"question_text": "What is the chemical formula for sulfuric acid?", "options": ["$H_2SO_4$", "$HCl$", "$NaOH$", "$H_2O$"], "correct_answer": "$H_2SO_4$", "explanation": "Sulfuric acid is a strong mineral acid with the chemical formula H2SO4."
#            }
#            ]
#        }#

#        for course_name, questions_to_add in sample_questions.items():
#            course_obj = course_objects.get(course_name)
#            if course_obj:
#                for q_data in questions_to_add:
#                    question = db.query(Question).filter_by(question_text=q_data["question_text"]).first()
#                    if not question:
#                        correct_answer_index = q_data["options"].index(q_data["correct_answer"])
#                        question = Question(
#                            course=course_obj,
#                            question_text=q_data["question_text"],
#                            options=q_data["options"],
#                            correct_answer=correct_answer_index,
#                            explanation=q_data.get("explanation")
#                        )
#                        db.add(question)
#                        logger.info(f"  Added Question for {course_name}: {q_data['question_text'][:30]}...")

        db.commit()
        logger.info("\nDatabase seeding completed successfully!")

    except Exception as e:
        db.rollback()
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        db.close()



if __name__ == "__main__":
    seed_database()
