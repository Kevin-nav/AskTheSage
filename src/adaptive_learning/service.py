from sqlalchemy.orm import Session, aliased, joinedload
from sqlalchemy import func, case, and_, or_, text
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Tuple, Any
import logging
import random

# Project-specific imports
from .selector import UniversalQuestionSelector, UserPerformance, QuestionScore, SelectionReason
from ..models.models import (
    Question, UserAnswer, User, Course, QuizSession, QuizSessionQuestion, 
    InteractionLog, Program, Faculty, Level
)

class DatabaseQuestionSelector:
    """
    Database integration layer for the Universal Question Selection Algorithm.
    Connects the algorithm to the database structure.
    """
    
    def __init__(self, db_session: Session, selector_config: Dict = None):
        self.db = db_session
        self.selector = UniversalQuestionSelector(selector_config)
        self.logger = logging.getLogger(__name__)
    
    def get_adaptive_questions(self, 
                          user_id: int, 
                          course_id: int, 
                          quiz_length: int) -> Tuple[List[QuestionScore], float]:
        """
        Gets a list of adaptively selected questions and the user's skill level.
        """
        try:
            user_performance = self._get_user_performance_history(user_id, course_id)
            available_questions, question_metadata = self._get_questions_with_metadata(course_id)
            course = self.db.query(Course).filter_by(id=course_id).first()
            course_difficulty_range = (course.min_difficulty, course.max_difficulty) if course and course.min_difficulty is not None else (1.0, 5.0)
            
            user_skill_level = self.selector._estimate_user_skill_level(user_performance, course_difficulty_range)

            if not user_performance:
                selected_questions = self._handle_new_user(course_id, quiz_length)
            else:
                selected_questions = self.selector.select_questions(
                    user_performance=user_performance,
                    question_metadata=question_metadata,
                    course_difficulty_range=course_difficulty_range,
                    quiz_length=quiz_length
                )
            return selected_questions, user_skill_level
        except Exception as e:
            self.logger.exception(f"Error getting adaptive questions for user {user_id}")
            raise
    
    def _get_user_performance_history(self, user_id: int, course_id: int) -> List[UserPerformance]:
        """Fetch user's performance history for all questions in the course."""
        latest_answer_ids_subquery = self.db.query(func.max(UserAnswer.id).label('max_id')).join(Question, UserAnswer.question_id == Question.id).filter(UserAnswer.user_id == user_id, Question.course_id == course_id).group_by(UserAnswer.question_id).scalar_subquery()
        latest_answers_query = self.db.query(UserAnswer).filter(UserAnswer.id.in_(latest_answer_ids_subquery)).subquery('latest_answers_query')
        performance_stats_query = self.db.query(UserAnswer.question_id, func.count(UserAnswer.id).label('total_attempts'), func.sum(case((UserAnswer.is_correct == True, 1), else_=0)).label('total_correct'), func.max(Question.difficulty_score).label('difficulty_score')).join(Question, UserAnswer.question_id == Question.id).filter(UserAnswer.user_id == user_id, Question.course_id == course_id).group_by(UserAnswer.question_id).subquery('performance_stats')
        ua_alias = aliased(UserAnswer, latest_answers_query)
        results = self.db.query(ua_alias, performance_stats_query.c.total_attempts, performance_stats_query.c.total_correct, performance_stats_query.c.difficulty_score).join(performance_stats_query, ua_alias.question_id == performance_stats_query.c.question_id).all()
        performance_list = []
        for row in results:
            answer, total_attempts, total_correct, difficulty_score = row
            if answer:
                performance_list.append(UserPerformance(question_id=answer.question_id, correct_streak=answer.correct_streak or 0, last_attempt_correct=answer.is_correct, last_attempt_date=answer.timestamp, total_attempts=total_attempts or 0, total_correct=total_correct or 0, next_review_date=answer.next_review_date, difficulty_score=difficulty_score))
        return performance_list

    def _get_questions_with_metadata(self, course_id: int) -> Tuple[List[int], Dict[int, Dict]]:
        """Get all available questions for the course with their metadata."""
        results = self.db.query(Question.id, Question.difficulty_score).filter(Question.course_id == course_id).all()
        question_ids = [r.id for r in results]
        metadata = {r.id: {'difficulty_score': r.difficulty_score} for r in results}
        return question_ids, metadata
    
    def _handle_new_user(self, course_id: int, quiz_length: int) -> List[QuestionScore]:
        """Special handling for users with no performance history."""
        from ..config import DIFFICULTY_BANDS
        all_questions = self.db.query(Question.id, Question.difficulty_score).filter(Question.course_id == course_id).all()
        scored_questions = [q for q in all_questions if q.difficulty_score is not None]
        selected_ids = []
        strategy = 'random'
        if len(scored_questions) / len(all_questions) > 0.8:
            strategy = 'difficulty_ramp'
            easy = [q.id for q in scored_questions if q.difficulty_score <= DIFFICULTY_BANDS['easy']]
            medium = [q.id for q in scored_questions if DIFFICULTY_BANDS['easy'] < q.difficulty_score <= DIFFICULTY_BANDS['medium']]
            hard = [q.id for q in scored_questions if q.difficulty_score > DIFFICULTY_BANDS['medium']]
            self.selector.rng.shuffle(easy)
            self.selector.rng.shuffle(medium)
            self.selector.rng.shuffle(hard)
            easy_count, hard_count = int(quiz_length * 0.25), int(quiz_length * 0.25)
            medium_count = quiz_length - easy_count - hard_count
            selected_ids.extend(easy[:easy_count])
            selected_ids.extend(medium[:medium_count])
            selected_ids.extend(hard[:hard_count])
            if len(selected_ids) < quiz_length:
                remaining_pool = [q.id for q in scored_questions if q.id not in selected_ids]
                self.selector.rng.shuffle(remaining_pool)
                selected_ids.extend(remaining_pool[:quiz_length - len(selected_ids)])
        if not selected_ids:
            strategy = 'random'
            question_ids = [q.id for q in all_questions]
            self.selector.rng.shuffle(question_ids)
            selected_ids = question_ids[:quiz_length]
        return [QuestionScore(question_id=qid, score=50.0, reason=SelectionReason.NEW_QUESTION, metadata={'new_user_strategy': strategy}) for qid in selected_ids]

class AdaptiveQuizService:
    """Complete service layer that integrates the adaptive algorithm with the application."""
    
    def __init__(self, db_session: Session, config: Dict = None):
        self.db = db_session
        self.db_selector = DatabaseQuestionSelector(db_session, config)
        self.logger = logging.getLogger(__name__)
    
    def start_quiz(self, user_id: int, course_id: int, quiz_length: int = 20) -> Dict:
        """Main method to start an adaptive quiz."""
        try:
            if not isinstance(quiz_length, int) or quiz_length <= 0:
                raise ValueError("Quiz length must be a positive integer.")
            user, course = self.db.query(User).filter(User.id == user_id).first(), self.db.query(Course).filter(Course.id == course_id).first()
            if not user or not course:
                raise ValueError("Invalid user or course ID")
            if ongoing_session := self.db.query(QuizSession).filter(QuizSession.user_id == user_id, QuizSession.status == 'in_progress').first():
                ongoing_session.status = 'incomplete'
                self.db.commit()
            
            selected_questions, user_skill_level = self.db_selector.get_adaptive_questions(user_id, course_id, quiz_length)
            
            session = QuizSession(
                user_id=user_id, 
                course_id=course_id, 
                total_questions=quiz_length, 
                status='in_progress',
                initial_user_skill_level=user_skill_level
            )
            self.db.add(session)
            self.db.flush()

            if len(selected_questions) < quiz_length:
                self.db.rollback()
                return {'status': 'error', 'message': 'Not enough questions in the course to start a quiz.'}
            
            self._save_session_questions(session.id, selected_questions)
            self.db.commit()
            
            first_question = self.get_next_question(session.id)
            return {'status': 'success', 'session_id': session.id, 'first_question': first_question}
        except Exception as e:
            self.db.rollback()
            self.logger.exception(f"Failed to start quiz for user {user_id}")
            return {'status': 'error', 'message': f'An unexpected error occurred while starting the quiz.'}

    def _save_session_questions(self, session_id: int, selected_questions: List[QuestionScore]):
        self.db.bulk_save_objects([
            QuizSessionQuestion(
                session_id=session_id, 
                question_id=q_score.question_id, 
                order_number=i + 1, 
                selection_reason=q_score.reason.value, 
                selection_score=q_score.score,
                selection_metadata=q_score.metadata
            ) for i, q_score in enumerate(selected_questions)
        ])

    def get_next_question(self, session_id: int, reported_question_ids: List[int] = None) -> Optional[Dict]:
        """Get the next unanswered question in the session."""
        reported_question_ids = reported_question_ids or []
        sq = self.db.query(QuizSessionQuestion).filter(QuizSessionQuestion.session_id == session_id, QuizSessionQuestion.is_answered == False, ~QuizSessionQuestion.question_id.in_(reported_question_ids)).order_by(QuizSessionQuestion.order_number).first()
        if not sq or not (question := self.db.query(Question).filter(Question.id == sq.question_id).first()):
            return None
        return {'id': question.id, 'text': question.question_text, 'options': question.options, 'order': sq.order_number}

    def submit_answer(self, session_id: int, question_id: int, user_answer: str, time_taken: int) -> Dict:
        """Process a user's answer submission."""
        try:
            session = self.db.query(QuizSession).get(session_id)
            if not session or session.status != 'in_progress':
                return {'status': 'error', 'message': 'Invalid or completed session.'}
            question = self.db.query(Question).get(question_id)
            if not question:
                raise ValueError(f"Question with id {question_id} not found.")
            is_correct = user_answer is not None and question.correct_answer is not None and user_answer.strip().lower() == question.correct_answer.strip().lower()
            self.db.query(QuizSessionQuestion).filter(QuizSessionQuestion.session_id == session_id, QuizSessionQuestion.question_id == question_id).update({'is_answered': True, 'user_answer': user_answer, 'is_correct': is_correct, 'time_taken': time_taken, 'answered_at': datetime.now(timezone.utc)})
            self._update_user_answer_history(session.user_id, question_id, is_correct, time_taken)
            if question.total_attempts is None: question.total_attempts = 0
            if question.total_incorrect is None: question.total_incorrect = 0
            question.total_attempts += 1
            if not is_correct:
                question.total_incorrect += 1
            self._log_interaction(session, question_id, is_correct, time_taken)
            next_question = self.get_next_question(session_id)
            if not next_question:
                self._complete_session(session_id)
            self.db.commit()
            return {'status': 'success', 'is_correct': is_correct, 'correct_answer': question.correct_answer, 'explanation': question.explanation, 'next_question': next_question, 'quiz_completed': not next_question}
        except Exception as e:
            self.db.rollback()
            self.logger.exception(f"Failed to submit answer for session {session_id}")
            return {'status': 'error', 'message': f'An unexpected error occurred while submitting your answer.'}

    def _update_user_answer_history(self, user_id: int, question_id: int, is_correct: bool, time_taken: int):
        latest_answer = self.db.query(UserAnswer).filter(UserAnswer.user_id == user_id, UserAnswer.question_id == question_id).order_by(UserAnswer.timestamp.desc()).first()
        last_streak = latest_answer.correct_streak if latest_answer and latest_answer.correct_streak is not None else 0
        new_streak = (last_streak + 1) if is_correct else 0
        self.db.add(UserAnswer(user_id=user_id, question_id=question_id, is_correct=is_correct, time_taken=time_taken, correct_streak=new_streak, next_review_date=self.db_selector.selector.calculate_next_review_date(new_streak) if is_correct else None))

    def _log_interaction(self, session: QuizSession, question_id: int, is_correct: bool, time_taken: int):
        sq = self.db.query(QuizSessionQuestion).filter(QuizSessionQuestion.session_id == session.id, QuizSessionQuestion.question_id == question_id).first()
        attempt_count = self.db.query(InteractionLog).filter(InteractionLog.user_id == session.user_id, InteractionLog.question_id == question_id).count()
        self.db.add(InteractionLog(user_id=session.user_id, question_id=question_id, session_id=session.id, is_correct=is_correct, time_taken=time_taken, attempt_number=attempt_count + 1, was_weakness=(sq.selection_reason == SelectionReason.WEAKNESS.value if sq else False), was_srs=(sq.selection_reason == SelectionReason.SRS_DUE.value if sq else False), was_new=(sq.selection_reason == SelectionReason.NEW_QUESTION.value if sq else False), is_first_attempt=(attempt_count == 0)))

    def _complete_session(self, session_id: int):
        session = self.db.query(QuizSession).get(session_id)
        if not session: return
        session.status, session.completed_at = 'completed', datetime.now(timezone.utc)
        correct_count, reported_count = self.db.query(func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_correct == True), func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_reported == True)).filter(QuizSessionQuestion.session_id == session_id).one()
        scorable_questions = session.total_questions - reported_count
        session.final_score = (correct_count / scorable_questions) * 100 if scorable_questions > 0 else 0

    def skip_question(self, session_id: int, question_id: int) -> Optional[Question]:
        """Skips a question by marking it as answered incorrectly."""
        try:
            if self.submit_answer(session_id, question_id, user_answer="skipped", time_taken=0)['status'] == 'success':
                return self.db.query(Question).filter_by(id=question_id).first()
            return None
        except Exception as e:
            self.logger.exception(f"Failed to skip question {question_id} for session {session_id}")
            return None

    def end_quiz_early(self, session_id: int) -> Tuple[int, int]:
        """Ends a quiz session prematurely and calculates the final score."""
        try:
            session = self.db.query(QuizSession).filter_by(id=session_id).first()
            if not session or session.status != 'in_progress': return 0, 0
            session.completed_at, session.status = datetime.now(timezone.utc), 'incomplete'
            answered_count, correct_answers, reported_count = self.db.query(func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_answered == True), func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_correct == True), func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_reported == True)).filter(QuizSessionQuestion.session_id == session_id).one()
            scorable_questions = answered_count - reported_count
            session.final_score = (correct_answers / scorable_questions) * 100 if scorable_questions > 0 else 0
            self.db.commit()
            return correct_answers, scorable_questions
        except Exception as e:
            self.db.rollback()
            self.logger.exception(f"Failed to end quiz early for session {session_id}")
            return 0, 0

    def cancel_quiz_session(self, session_id: int) -> str:
        """Cancels a quiz session, deleting or scoring it based on progress."""
        try:
            session = self.db.query(QuizSession).filter_by(id=session_id).first()
            if not session: return "NOT_FOUND"
            if not self.db.query(QuizSessionQuestion).filter_by(session_id=session_id, is_answered=True).count():
                self.db.query(QuizSessionQuestion).filter_by(session_id=session_id).delete(synchronize_session=False)
                self.db.delete(session)
                self.db.commit()
                return "DELETED"
            else:
                correct_answers = self.db.query(QuizSessionQuestion).filter_by(session_id=session_id, is_correct=True).count()
                answered_count = self.db.query(QuizSessionQuestion).filter_by(session_id=session_id, is_answered=True).count()
                session.completed_at, session.status = datetime.now(timezone.utc), 'cancelled'
                session.final_score = (correct_answers / answered_count) * 100 if answered_count > 0 else 0
                self.db.commit()
                return "SCORED"
        except Exception as e:
            self.db.rollback()
            self.logger.exception(f"Failed to cancel quiz session {session_id}")
            return "ERROR"

    def get_quiz_results(self, session_id: int) -> Optional[QuizSession]:
        """Get the results of a completed quiz session."""
        return self.db.query(QuizSession).filter_by(id=session_id).first()

    def get_user_performance_data(self, telegram_id: int) -> Dict[str, Any]:
        """
        Get a comprehensive performance report for a user, including lifetime stats,
        categorized course performance, and recent quiz activity.
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return {"status": "not_found", "message": "User not found."}
            
            preferred_program_id = user.preferred_program_id

            lifetime_stats = self.db.query(
                func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_answered == True),
                func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_correct == True)
            ).join(QuizSession).filter(QuizSession.user_id == user.id).one()
            total_answered, total_correct = lifetime_stats

            course_performance_query = self.db.query(
                Course.name,
                func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_correct == True).label("correct"),
                func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_answered == True).label("answered"),
                case((Course.programs.any(Program.id == preferred_program_id), True), else_=False).label("is_preferred")
            ).\
                join(QuizSession, QuizSession.course_id == Course.id).\
                join(QuizSessionQuestion, QuizSessionQuestion.session_id == QuizSession.id).\
                filter(QuizSession.user_id == user.id).\
                group_by(Course.id).all()

            categorized_performance = {"preferred_courses": [], "other_courses": []}
            for course_name, correct, answered, is_preferred in course_performance_query:
                if answered > 0:
                    accuracy = (correct / answered) * 100
                    course_data = {"course_name": course_name, "accuracy": accuracy}
                    if is_preferred:
                        categorized_performance["preferred_courses"].append(course_data)
                    else:
                        categorized_performance["other_courses"].append(course_data)

            last_three_sessions = self.db.query(QuizSession).filter(
                QuizSession.user_id == user.id,
                QuizSession.status.in_(['completed', 'incomplete', 'cancelled'])
            ).options(joinedload(QuizSession.course)).order_by(QuizSession.completed_at.desc()).limit(3).all()

            recent_quizzes_data = []
            for session in last_three_sessions:
                session_stats = self.db.query(
                    func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_answered == True),
                    func.count(QuizSessionQuestion.id).filter(QuizSessionQuestion.is_correct == True)
                ).filter(QuizSessionQuestion.session_id == session.id).one()
                answered_in_session, correct_in_session = session_stats
                recent_quizzes_data.append({
                    "course_name": session.course.name if session.course else "Unknown Course",
                    "answered_count": answered_in_session,
                    "correct_count": correct_in_session,
                    "status": session.status
                })

            return {
                "status": "success",
                "lifetime_stats": {"total_answered": total_answered, "total_correct": total_correct},
                "categorized_performance": categorized_performance,
                "recent_quizzes": recent_quizzes_data
            }

        except Exception as e:
            self.logger.exception(f"Failed to get user performance data for telegram_id {telegram_id}")
            return {"status": "error", "message": "An error occurred while fetching performance data."}
