from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import func, case
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

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
    Uses the new AdaptiveQuizService if enabled, falls back to legacy logic otherwise.
    """
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        # Create new user if doesn't exist
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
            # Handle error case
            logging.error(f"Adaptive quiz start failed: {result['message']}")
            raise Exception(f"Could not start adaptive quiz: {result['message']}")
    
    else:
        # --- LEGACY QUIZ LOGIC (FALLBACK) ---
        logging.info(f"Starting legacy quiz for user {user.id} in course {course_id}")
        
        # Deactivate any previous active sessions
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
            questions_count=len(selected_questions),
            is_active=True,
            status='in_progress'
        )
        db.add(new_session)
        db.flush()

        if selected_questions:
            for question in selected_questions:
                session_question = QuizSessionQuestion(
                    session_id=new_session.id, 
                    question_id=question.id
                )
                db.add(session_question)

        db.commit()
        return new_session


def get_next_question_for_session(db: Session, session_id: int, reported_question_ids: List[int] = None) -> Optional[Question]:
    """
    Gets the next unanswered question for a given quiz session.
    """
    if reported_question_ids is None:
        reported_question_ids = []
        
    session = db.query(QuizSession).filter_by(id=session_id).first()
    if not session:
        return None
    
    if ADAPTIVE_QUIZ_ENABLED:
        adaptive_service = get_adaptive_service(db, session.course_id)
        next_q_data = adaptive_service.get_next_question(session_id, reported_question_ids)
        if next_q_data:
            return db.query(Question).filter_by(id=next_q_data['id']).first()
        return None

    else:
        # --- LEGACY LOGIC ---
        session_question = (
            db.query(QuizSessionQuestion)
            .filter(
                QuizSessionQuestion.session_id == session_id,
                QuizSessionQuestion.is_answered == False,
                ~QuizSessionQuestion.question_id.in_(reported_question_ids)
            )
            .first()
        )
        if session_question:
            return db.query(Question).filter_by(id=session_question.question_id).first()
        return None


def submit_answer(db: Session, session_id: int, question_id: int, user_answer: str, time_taken: int) -> bool:
    """
    Records the user's answer. Uses the new AdaptiveQuizService if enabled.
    Returns whether the answer was correct.
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
        session_question.is_correct = is_correct
        session_question.user_answer = user_answer
        session_question.time_taken = time_taken
        session_question.answered_at = datetime.now(timezone.utc)
        
        if is_correct:
            session.correct_answers += 1

        user_answer_record = UserAnswer(
            user_id=session.user_id,
            question_id=question_id,
            is_correct=is_correct,
            time_taken=time_taken
        )
        db.add(user_answer_record)
        db.commit()
        return is_correct


def skip_question(db: Session, session_id: int, question_id: int) -> Optional[Question]:
    """
    Skips a question by marking it as answered incorrectly.
    """
    session = db.query(QuizSession).filter_by(id=session_id).first()
    if not session:
        return None

    if ADAPTIVE_QUIZ_ENABLED:
        adaptive_service = get_adaptive_service(db, session.course_id)
        result = adaptive_service.skip_question(session_id, question_id)
        return result
    else:
        # --- LEGACY LOGIC ---
        # Mark as answered with incorrect result
        submit_answer(db, session_id, question_id, user_answer="skipped", time_taken=0)
        return db.query(Question).filter_by(id=question_id).first()


def end_quiz_early(db: Session, session_id: int) -> Tuple[int, int]:
    """
    Ends a quiz session prematurely (e.g., due to timeout) and calculates the final score.
    Returns (correct_answers, total_answered_questions).
    """
    if ADAPTIVE_QUIZ_ENABLED:
        session = db.query(QuizSession).filter_by(id=session_id).first()
        if session:
            adaptive_service = get_adaptive_service(db, session.course_id)
            return adaptive_service.end_quiz_early(session_id)
        return 0, 0
    else:
        # --- LEGACY LOGIC ---
        session = db.query(QuizSession).filter_by(id=session_id).first()
        if not session:
            return 0, 0

        session.is_completed = True
        session.completed_at = datetime.now(timezone.utc)
        session.status = 'incomplete'

        # Get counts of answered, correct, and reported questions
        counts = db.query(
            func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_answered == True),
            func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_correct == True),
            func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_reported == True)
        ).filter(QuizSessionQuestion.session_id == session_id).one()

        answered_count = counts[0]
        correct_answers = counts[1]
        reported_count = counts[2]

        scorable_answered_count = answered_count - reported_count

        if scorable_answered_count > 0:
            session.final_score = (correct_answers / scorable_answered_count) * 100
        else:
            session.final_score = 0
            
        db.commit()
        return correct_answers, scorable_answered_count


def complete_quiz_session(db: Session, session_id: int) -> Optional[QuizSession]:
    """
    Marks a quiz session as completed and calculates the final score.
    This now acts as a wrapper around the adaptive service's completion logic.
    """
    session = db.query(QuizSession).filter_by(id=session_id).first()
    if not session:
        return None

    if ADAPTIVE_QUIZ_ENABLED:
        adaptive_service = get_adaptive_service(db, session.course_id)
        # This calls the internal method of the adaptive service to finalize the session
        adaptive_service._complete_session(session_id)
        db.refresh(session) # Refresh to get the updated final_score
    else:
        # --- LEGACY LOGIC ---
        session.status = 'completed'
        session.completed_at = datetime.now(timezone.utc)
        
        correct_answers, answered_count, reported_count = db.query(
            func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_correct == True),
            func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_answered == True),
            func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_reported == True)
        ).filter(QuizSessionQuestion.session_id == session_id).one()

        scorable_answered_count = answered_count - reported_count
        if scorable_answered_count > 0:
            session.final_score = (correct_answers / scorable_answered_count) * 100
        else:
            session.final_score = 0
        db.commit()
        db.refresh(session)
        
    return session


def get_quiz_results(db: Session, session_id: int) -> Optional[QuizSession]:
    """
    Get the results of a completed quiz session.
    """
    return db.query(QuizSession).filter_by(id=session_id).first()


def cancel_quiz_session(db: Session, session_id: int) -> str:
    """
    Cancels a quiz session. Deletes it if no questions were answered, otherwise scores it.
    """
    if ADAPTIVE_QUIZ_ENABLED:
        session = db.query(QuizSession).filter_by(id=session_id).first()
        if session:
            adaptive_service = get_adaptive_service(db, session.course_id)
            return adaptive_service.cancel_quiz_session(session_id)
        return "NOT_FOUND"
    else:
        # --- LEGACY LOGIC ---
        session = db.query(QuizSession).filter_by(id=session_id).first()
        if not session:
            return "NOT_FOUND"

        answered_count = db.query(QuizSessionQuestion).filter_by(
            session_id=session_id, 
            is_answered=True
        ).count()

        if answered_count == 0:
            # User changed their mind - delete the session as if it never happened.
            db.query(QuizSessionQuestion).filter_by(session_id=session_id).delete(synchronize_session=False)
            db.delete(session)
            db.commit()
            return "DELETED"
        else:
            # User made progress - score what they did and mark as cancelled.
            correct_answers = db.query(QuizSessionQuestion).filter_by(
                session_id=session_id, 
                is_correct=True
            ).count()
            
            session.completed_at = datetime.now(timezone.utc)
            session.status = 'cancelled'
            session.final_score = (correct_answers / answered_count) * 100
            db.commit()
            return "SCORED"


def get_user_performance_data(db: Session, telegram_id: int) -> Dict[str, Any]:
    """
    Get comprehensive performance data for a user.
    """
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        return {
            "total_quizzes": 0, 
            "overall_average_score": 0, 
            "categorized_performance": {}, 
            "other_courses_performance": {}
        }

    if ADAPTIVE_QUIZ_ENABLED:
        # Use the enhanced adaptive service method
        adaptive_service = AdaptiveQuizService(db)
        return adaptive_service.get_user_performance_data(user.id)
    else:
        # --- LEGACY PERFORMANCE DATA LOGIC ---
        from src.models.models import Program, Faculty
        
        # Fetch preferred program and faculty for the user
        preferred_program_id = user.preferred_program_id

        # Fetch all completed quiz sessions for the user
        completed_quizzes = db.query(QuizSession).filter(
            QuizSession.user_id == user.id,
            QuizSession.status == 'completed',
            QuizSession.final_score != None
        ).options(
            joinedload(QuizSession.course).joinedload(Course.programs).joinedload(Program.faculty),
            joinedload(QuizSession.course).joinedload(Course.level)
        ).order_by(QuizSession.completed_at.desc()).all()

        if not completed_quizzes:
            return {
                "total_quizzes": 0, 
                "overall_average_score": 0, 
                "categorized_performance": {}, 
                "other_courses_performance": {}
            }

        total_quizzes = len(completed_quizzes)
        total_score_sum = sum(session.final_score for session in completed_quizzes)
        overall_average_score = total_score_sum / total_quizzes

        categorized_performance: Dict[str, Dict[str, Dict[str, Any]]] = {}
        other_courses_performance: Dict[str, Any] = {}

        for session in completed_quizzes:
            course = session.course
            if not course:
                continue

            course_name = course.name
            session_score = session.final_score
            session_date = session.completed_at.strftime("%Y-%m-%d") if session.completed_at else "N/A"

            # Determine if the course belongs to the user's preferred program
            is_preferred_course = False
            if preferred_program_id and course.programs:
                for program in course.programs:
                    if program.id == preferred_program_id:
                        is_preferred_course = True
                        break
            
            if is_preferred_course:
                program_for_course = next((p for p in course.programs if p.id == preferred_program_id), None)
                faculty_for_course = program_for_course.faculty if program_for_course and program_for_course.faculty else None

                faculty_name = faculty_for_course.name if faculty_for_course else "Unknown Faculty"
                program_name = program_for_course.name if program_for_course else "Unknown Program"

                course_data = categorized_performance.setdefault(faculty_name, {}).setdefault(program_name, {}).setdefault(course_name, {
                    "total_quizzes_in_course": 0,
                    "total_score_sum_in_course": 0,
                    "recent_quizzes_in_course": []
                })
            else:
                course_data = other_courses_performance.setdefault(course_name, {
                    "total_quizzes_in_course": 0,
                    "total_score_sum_in_course": 0,
                    "recent_quizzes_in_course": []
                })

            course_data["total_quizzes_in_course"] += 1
            course_data["total_score_sum_in_course"] += session_score
            
            if len(course_data["recent_quizzes_in_course"]) < 5:
                course_data["recent_quizzes_in_course"].append({
                    "score": session_score,
                    "date": session_date
                })

        # Calculate average scores for each course
        for faculty_name, programs_data in categorized_performance.items():
            for program_name, courses_data in programs_data.items():
                for course_name, data in courses_data.items():
                    data["average_score_in_course"] = data["total_score_sum_in_course"] / data["total_quizzes_in_course"] if data["total_quizzes_in_course"] > 0 else 0
        
        for course_name, data in other_courses_performance.items():
            data["average_score_in_course"] = data["total_score_sum_in_course"] / data["total_quizzes_in_course"] if data["total_quizzes_in_course"] > 0 else 0

        return {
            "total_quizzes": total_quizzes,
            "overall_average_score": overall_average_score,
            "categorized_performance": categorized_performance,
            "other_courses_performance": other_courses_performance
        }