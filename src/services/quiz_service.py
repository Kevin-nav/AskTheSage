from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import func, case
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any # Added Dict, Any # Added this import

# Import models and config
from src.models.models import (
    User, Course, Question, UserAnswer, QuizSession, QuizSessionQuestion
)
from src.config import ADAPTIVE_QUIZ_ENABLED, ADAPTIVE_QUIZ_CONFIG, COURSE_CONFIGS

# Import the new adaptive service
from src.adaptive_learning.service import AdaptiveQuizService


def get_adaptive_service(db: Session, course_id: int) -> AdaptiveQuizService:
    """Helper function to initialize the adaptive service with course-specific config."""
    course = db.query(Course).filter_by(id=course_id).first()
    course_name = course.name if course else ""
    
    # Get base config and merge course-specific overrides
    config = ADAPTIVE_QUIZ_CONFIG.copy()
    course_specific_config = COURSE_CONFIGS.get(course_name.lower(), {})
    config.update(course_specific_config)
    
    return AdaptiveQuizService(db, config)


def start_new_quiz(db: Session, telegram_id: int, course_id: int, quiz_length: int) -> QuizSession:
    """
    Starts a new quiz session for a user.
    Uses the new AdaptiveQuizService if enabled.
    """
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    if ADAPTIVE_QUIZ_ENABLED:
        logging.info(f"Starting adaptive quiz for user {user.id} in course {course_id}")
        adaptive_service = get_adaptive_service(db, course_id)
        result = adaptive_service.start_quiz(user.id, course_id, quiz_length)
        
        if result['status'] == 'success':
            # The function must return a QuizSession object, so we fetch it
            session = db.query(QuizSession).filter_by(id=result['session_id']).first()
            return session
        else:
            # Handle error case, maybe raise an exception or return None
            logging.error(f"Adaptive quiz start failed: {result['message']}")
            raise Exception(f"Could not start adaptive quiz: {result['message']}")
    
    else:
        # --- LEGACY QUIZ LOGIC ---
        logging.info(f"Starting legacy quiz for user {user.id} in course {course_id}")
        db.query(QuizSession).filter_by(user_id=user.id, is_active=True).update({"is_active": False})

        # Legacy question selection logic
        latest_answer_subquery = (
            db.query(
                UserAnswer.question_id,
                UserAnswer.is_correct,
                func.row_number()
                .over(
                    partition_by=UserAnswer.question_id,
                    order_by=UserAnswer.timestamp.desc()
                )
                .label("rn"),
            )
            .filter(UserAnswer.user_id == user.id)
            .subquery("latest_answers")
        )
        la = aliased(latest_answer_subquery)
        score_logic = case(
            (la.c.is_correct == False, 100),
            (la.c.is_correct == None, 50),
            (la.c.is_correct == True, 1),
        ).label("score")
        selected_questions = (
            db.query(Question)
            .outerjoin(la, (la.c.question_id == Question.id) & (la.c.rn == 1))
            .filter(Question.course_id == course_id)
            .order_by(score_logic.desc())
            .limit(quiz_length)
            .all()
        )

        new_session = QuizSession(
            user_id=user.id, 
            course_id=course_id,
            questions_count=len(selected_questions)
        )
        db.add(new_session)
        db.flush()

        if selected_questions:
            for question in selected_questions:
                session_question = QuizSessionQuestion(
                    session_id=new_session.id, question_id=question.id
                )
                db.add(session_question)

        db.commit()
        return new_session


def get_next_question_for_session(db: Session, session_id: int, reported_question_ids: List[int]) -> Question | None:
    """
    Gets the next unanswered question for a given quiz session.
    """
    session = db.query(QuizSession).filter_by(id=session_id).first()
    
    if ADAPTIVE_QUIZ_ENABLED:
        adaptive_service = get_adaptive_service(db, session.course_id)
        next_q_data = adaptive_service.get_next_question(session_id, reported_question_ids)
        if next_q_data:
            return db.query(Question).filter_by(id=next_q_data['id']).first()
        return None

    # --- LEGACY LOGIC ---
    session_question = (
        db.query(QuizSessionQuestion)
        .filter_by(session_id=session_id, is_answered=False)
        .first()
    )
    if session_question:
        return db.query(Question).filter_by(id=session_question.question_id).first()
    return None


def submit_answer(db: Session, session_id: int, question_id: int, user_answer: str, time_taken: int) -> bool:
    """
    Records the user's answer. Uses the new AdaptiveQuizService if enabled.
    Note: The signature is changed to accept user_answer (string) and time_taken.
    """
    session = db.query(QuizSession).options(joinedload(QuizSession.user)).filter_by(id=session_id).first()
    if not session:
        return False

    if ADAPTIVE_QUIZ_ENABLED:
        adaptive_service = get_adaptive_service(db, session.course_id)
        result = adaptive_service.submit_answer(session_id, question_id, user_answer, time_taken)
        return result.get('is_correct', False)

    else:
        # --- LEGACY LOGIC ---
        question = db.query(Question).filter_by(id=question_id).first()
        if not question:
            return False
        
        is_correct = user_answer == str(question.correct_answer)

        session_question = (
            db.query(QuizSessionQuestion)
            .filter(QuizSessionQuestion.session_id == session_id)
            .filter(QuizSessionQuestion.question_id == question_id)
            .first()
        )
        if not session_question:
            return False

        session_question.is_answered = True
        if is_correct:
            session.correct_answers += 1

        user_answer_record = UserAnswer(
            user_id=session.user_id,
            question_id=question_id,
            is_correct=is_correct,
        )
        db.add(user_answer_record)
        db.commit()
        return is_correct


def skip_question(db: Session, session_id: int, question_id: int) -> Question | None:
    """
    Skips a question by marking it as answered incorrectly.
    """
    session = db.query(QuizSession).filter_by(id=session_id).first()
    if not session:
        return None

    # Use the adaptive service to handle the logic
    adaptive_service = get_adaptive_service(db, session.course_id)
    
    # Mark as answered, incorrect, with zero time taken
    result = adaptive_service.submit_answer(session_id, question_id, user_answer="skipped", time_taken=0)
    
    if result['status'] == 'success':
        return db.query(Question).filter_by(id=question_id).first()
    
    return None


def end_quiz_early(db: Session, session_id: int) -> tuple[int, int]:
    """
    Ends the quiz session prematurely and calculates the final score.
    """
    session = db.query(QuizSession).filter_by(id=session_id).first()
    if not session:
        return 0, 0

    session.is_completed = True
    session.completed_at = datetime.now(timezone.utc)
    
    # Calculate score based on answered questions
    answered_questions = db.query(QuizSessionQuestion).filter(
        QuizSessionQuestion.session_id == session_id,
        QuizSessionQuestion.is_answered == True
    ).all()
    
    correct_answers = sum(1 for q in answered_questions if q.is_correct)
    answered_count = len(answered_questions)
    
    if answered_count > 0:
        session.final_score = (correct_answers / answered_count) * 100
    else:
        session.final_score = 0
        
    db.commit()
    
    return correct_answers, answered_count


def get_quiz_results(db: Session, session_id: int) -> QuizSession | None:
    return db.query(QuizSession).filter_by(id=session_id).first()

def cancel_quiz_session(db: Session, session_id: int):
    session = db.query(QuizSession).filter_by(id=session_id).first()
    if session:
        session.is_completed = True
        session.completed_at = datetime.now(timezone.utc)
        session.final_score = 0 # Or some other indicator for cancelled quiz
        db.commit()

def get_user_performance_data(db: Session, telegram_id: int) -> Dict[str, Any]:
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        return {"total_quizzes": 0, "overall_average_score": 0, "categorized_performance": {}, "other_courses_performance": {}}

    # Fetch preferred program and faculty for the user
    preferred_program_id = user.preferred_program_id
    preferred_faculty_id = user.preferred_faculty_id

    # Fetch all completed quiz sessions for the user, eagerly loading related course, program, and faculty data
    completed_quizzes = db.query(QuizSession).filter(
        QuizSession.user_id == user.id,
        QuizSession.is_completed == True,
        QuizSession.final_score != None  # Ensure only graded quizzes are included
    ).options(
        joinedload(QuizSession.course).joinedload(Course.programs),
        joinedload(QuizSession.course).joinedload(Course.level),
        joinedload(QuizSession.user).joinedload(User.preferred_faculty),
        joinedload(QuizSession.user).joinedload(User.preferred_program)
    ).order_by(QuizSession.completed_at.desc()).all()

    if not completed_quizzes:
        return {"total_quizzes": 0, "overall_average_score": 0, "categorized_performance": {}, "other_courses_performance": {}}

    total_quizzes = len(completed_quizzes)
    total_score_sum = sum(session.final_score for session in completed_quizzes)
    overall_average_score = total_score_sum / total_quizzes

    categorized_performance: Dict[str, Dict[str, Dict[str, Any]]] = {}
    other_courses_performance: Dict[str, Any] = {}

    for session in completed_quizzes:
        course = session.course
        if not course:
            continue # Skip if course data is missing

        course_name = course.name
        session_score = session.final_score
        session_date = session.completed_at.strftime("%Y-%m-%d %H:%M")

        # Determine if the course belongs to the user's preferred program
        is_preferred_course = False
        if preferred_program_id and course.programs:
            for program in course.programs:
                if program.id == preferred_program_id:
                    is_preferred_course = True
                    break
        
        if is_preferred_course:
            # Get faculty and program names for categorization
            # Assuming a course belongs to at least one program, and that program has a faculty
            program_for_course = next((p for p in course.programs if p.id == preferred_program_id), None)
            faculty_for_course = program_for_course.faculty if program_for_course and program_for_course.faculty else None

            faculty_name = faculty_for_course.name if faculty_for_course else "Unknown Faculty"
            program_name = program_for_course.name if program_for_course else "Unknown Program"

            if faculty_name not in categorized_performance:
                categorized_performance[faculty_name] = {}
            if program_name not in categorized_performance[faculty_name]:
                categorized_performance[faculty_name][program_name] = {}
            if course_name not in categorized_performance[faculty_name][program_name]:
                categorized_performance[faculty_name][program_name][course_name] = {
                    "total_quizzes_in_course": 0,
                    "total_score_sum_in_course": 0,
                    "recent_quizzes_in_course": []
                }
            
            course_data = categorized_performance[faculty_name][program_name][course_name]
        else:
            # Course is outside preferred program or preferred program not set
            if course_name not in other_courses_performance:
                other_courses_performance[course_name] = {
                    "total_quizzes_in_course": 0,
                    "total_score_sum_in_course": 0,
                    "recent_quizzes_in_course": []
                }
            course_data = other_courses_performance[course_name]

        course_data["total_quizzes_in_course"] += 1
        course_data["total_score_sum_in_course"] += session_score
        
        # Add to recent quizzes for this course, keeping only the 5 most recent
        course_data["recent_quizzes_in_course"].insert(0, { # Insert at beginning to keep it ordered by most recent
            "score": session_score,
            "date": session_date
        })
        course_data["recent_quizzes_in_course"] = course_data["recent_quizzes_in_course"][:5]

    # Calculate average scores for each course
    for faculty_name, programs_data in categorized_performance.items():
        for program_name, courses_data in programs_data.items():
            for course_name, data in courses_data.items():
                if data["total_quizzes_in_course"] > 0:
                    data["average_score_in_course"] = data["total_score_sum_in_course"] / data["total_quizzes_in_course"]
                else:
                    data["average_score_in_course"] = 0
    
    for course_name, data in other_courses_performance.items():
        if data["total_quizzes_in_course"] > 0:
            data["average_score_in_course"] = data["total_score_sum_in_course"] / data["total_quizzes_in_course"]
        else:
            data["average_score_in_course"] = 0

    return {
        "total_quizzes": total_quizzes,
        "overall_average_score": overall_average_score,
        "categorized_performance": categorized_performance,
        "other_courses_performance": other_courses_performance
    }