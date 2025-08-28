from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, case, and_, or_, text
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Tuple
import logging
import random

# Project-specific imports
from .selector import UniversalQuestionSelector, UserPerformance, QuestionScore, SelectionReason
from ..models.models import Question, UserAnswer, User, Course, QuizSession, QuizSessionQuestion, InteractionLog

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
                          quiz_length: int) -> List[QuestionScore]:
        """
        Gets a list of adaptively selected questions.
        """
        try:
            # Step 1: Get user's performance history for this course
            user_performance = self._get_user_performance_history(user_id, course_id)
            
            # Step 2: Get all available questions for the course
            available_questions = self._get_available_questions(course_id)
            
            # Step 3: Check if this is a new user (special handling)
            if not user_performance:
                selected_questions = self._handle_new_user(course_id, quiz_length)
            else:
                # Step 4: Use the universal algorithm to select questions
                selected_questions = self.selector.select_questions(
                    user_id=user_id,
                    course_id=course_id,
                    quiz_length=quiz_length,
                    user_performance=user_performance,
                    available_questions=available_questions
                )
            
            return selected_questions
            
        except Exception as e:
            self.logger.exception(f"Error getting adaptive questions for user {user_id}")
            raise
    
    def _get_user_performance_history(self, user_id: int, course_id: int) -> List[UserPerformance]:
        """
        Fetch user's performance history for all questions in the course.
        """
        
        # Subquery to get the most recent answer for each question
        latest_answer_subquery = (
            self.db.query(
                UserAnswer.question_id,
                func.max(UserAnswer.timestamp).label('max_timestamp')
            )
            .join(Question, UserAnswer.question_id == Question.id)
            .filter(
                UserAnswer.user_id == user_id,
                Question.course_id == course_id
            )
            .group_by(UserAnswer.question_id)
            .subquery('latest_answer_subquery')
        )

        # Join to get the full details of the latest answer
        latest_answers_query = (
            self.db.query(UserAnswer)
            .join(
                latest_answer_subquery,
                and_(
                    UserAnswer.question_id == latest_answer_subquery.c.question_id,
                    UserAnswer.timestamp == latest_answer_subquery.c.max_timestamp
                )
            )
        )
        
        # Subquery to get aggregated stats (total attempts, total correct)
        performance_stats_query = (
            self.db.query(
                UserAnswer.question_id,
                func.count(UserAnswer.id).label('total_attempts'),
                func.sum(case((UserAnswer.is_correct == True, 1), else_=0)).label('total_correct')
            )
            .join(Question, UserAnswer.question_id == Question.id)
            .filter(
                UserAnswer.user_id == user_id,
                Question.course_id == course_id
            )
            .group_by(UserAnswer.question_id)
            .subquery('performance_stats')
        )
        
        # Alias the UserAnswer model to the subquery of latest answers
        ua_alias = aliased(UserAnswer, latest_answers_query.subquery())

        results = (
            self.db.query(
                ua_alias,
                performance_stats_query.c.total_attempts,
                performance_stats_query.c.total_correct
            )
            .outerjoin(
                performance_stats_query,
                ua_alias.question_id == performance_stats_query.c.question_id
            )
            .all()
        )

        performance_list = []
        for row in results:
            answer, total_attempts, total_correct = row
            if answer:
                performance = UserPerformance(
                    question_id=answer.question_id,
                    correct_streak=answer.correct_streak or 0,
                    last_attempt_correct=answer.is_correct,
                    last_attempt_date=answer.timestamp,
                    total_attempts=total_attempts or 0,
                    total_correct=total_correct or 0,
                    next_review_date=answer.next_review_date
                )
                performance_list.append(performance)
        
        return performance_list

    def _get_available_questions(self, course_id: int) -> List[int]:
        """
        Get all question IDs available for the course.
        """
        results = (
            self.db.query(Question.id)
            .filter(Question.course_id == course_id)
            .all()
        )
        return [result[0] for result in results]
    
    def _handle_new_user(self, course_id: int, quiz_length: int) -> List[QuestionScore]:
        """
        Special handling for users with no performance history.
        Creates a balanced introduction using difficulty scores if available.
        """
        all_questions = (
            self.db.query(Question.id, Question.difficulty_score)
            .filter(Question.course_id == course_id)
            .all()
        )
        
        # If difficulty scores are available, create a ramped quiz
        if all(q.difficulty_score is not None for q in all_questions):
            easy = [q.id for q in all_questions if q.difficulty_score <= 1.5]
            medium = [q.id for q in all_questions if 1.5 < q.difficulty_score <= 3.0]
            hard = [q.id for q in all_questions if q.difficulty_score > 3.0]
            
            self.selector.rng.shuffle(easy)
            self.selector.rng.shuffle(medium)
            self.selector.rng.shuffle(hard)

            # Proportional selection
            easy_count = int(quiz_length * 0.25) # 25% easy
            hard_count = int(quiz_length * 0.25) # 25% hard
            medium_count = quiz_length - easy_count - hard_count # 50% medium

            selected_ids = easy[:easy_count] + medium[:medium_count] + hard[:hard_count]
            
            # Fill if any category was short
            remaining_ids = (
                [qid for qid in easy + medium + hard if qid not in selected_ids]
            )
            self.selector.rng.shuffle(remaining_ids)
            selected_ids.extend(remaining_ids)
            selected_ids = selected_ids[:quiz_length]

        else: # Fallback to random selection
            question_ids = [q.id for q in all_questions]
            self.selector.rng.shuffle(question_ids)
            selected_ids = question_ids[:quiz_length]

        # Create QuestionScore objects
        selected = [
            QuestionScore(
                question_id=qid,
                score=50.0,
                reason=SelectionReason.NEW_QUESTION,
                metadata={'new_user_strategy': 'difficulty_ramp' if all(q.difficulty_score is not None for q in all_questions) else 'random'}
            ) for qid in selected_ids
        ]
        self.selector.rng.shuffle(selected) # Shuffle the final list
        return selected

class AdaptiveQuizService:
    """
    Service layer that integrates the adaptive algorithm with the application.
    This replaces or enhances the current quiz_service.py.
    """
    
    def __init__(self, db_session: Session, config: Dict = None):
        self.db = db_session
        self.db_selector = DatabaseQuestionSelector(db_session, config)
    
    def start_quiz(self, user_id: int, course_id: int, quiz_length: int = 20) -> Dict:
        """
        Main method to start an adaptive quiz.
        """
        try:
            if not isinstance(quiz_length, int) or quiz_length <= 0:
                raise ValueError("Quiz length must be a positive integer.")

            # Validate inputs
            user = self.db.query(User).filter(User.id == user_id).first()
            course = self.db.query(Course).filter(Course.id == course_id).first()
            
            if not user or not course:
                raise ValueError("Invalid user or course ID")
            
            # NOTE: There is a potential race condition here. Two concurrent requests
            # could both find no ongoing session and then both create one.
            # A unique constraint in the database is the best fix.
            # e.g., UNIQUE(user_id) WHERE is_completed = FALSE
            ongoing_session = self.db.query(QuizSession).filter(
                QuizSession.user_id == user_id,
                QuizSession.is_completed == False
            ).first()
            
            if ongoing_session:
                return {'status': 'error', 'message': 'You have an ongoing quiz.'}

            # Create the quiz session
            session = QuizSession(
                user_id=user_id,
                course_id=course_id,
                total_questions=quiz_length,
                is_completed=False
            )
            self.db.add(session)
            self.db.flush()

            # Get questions
            selected_questions = self.db_selector.get_adaptive_questions(
                user_id, course_id, quiz_length
            )
            
            if len(selected_questions) < quiz_length:
                self.db.rollback()
                return {'status': 'error', 'message': 'Not enough questions in the course to start a quiz.'}

            # Save questions to the session
            self._save_session_questions(session.id, selected_questions)
            
            self.db.commit()
            
            first_question = self.get_next_question(session.id)

            return {
                'status': 'success',
                'session_id': session.id,
                'first_question': first_question
            }
            
        except Exception as e:
            self.db.rollback()
            logging.exception(f"Failed to start quiz for user {user_id}")
            return {'status': 'error', 'message': f'An unexpected error occurred while starting the quiz.'}

    def _save_session_questions(self, session_id: int, selected_questions: List[QuestionScore]):
        session_questions = []
        for i, q_score in enumerate(selected_questions):
            sq = QuizSessionQuestion(
                session_id=session_id,
                question_id=q_score.question_id,
                order_number=i + 1,
                selection_reason=q_score.reason.value,
                selection_score=q_score.score
            )
            session_questions.append(sq)
        self.db.bulk_save_objects(session_questions)

    def get_next_question(self, session_id: int, reported_question_ids: List[int] = None) -> Optional[Dict]:
        """
        Get the next unanswered question in the session, excluding reported questions.
        """
        if reported_question_ids is None:
            reported_question_ids = []

        sq = self.db.query(QuizSessionQuestion).filter(
            QuizSessionQuestion.session_id == session_id,
            QuizSessionQuestion.is_answered == False,
            ~QuizSessionQuestion.question_id.in_(reported_question_ids) # Exclude reported questions
        ).order_by(QuizSessionQuestion.order_number).first()

        if not sq:
            return None

        question = self.db.query(Question).filter(Question.id == sq.question_id).first()
        if not question:
            return None # Should not happen if DB is consistent

        return {
            'id': question.id,
            'text': question.question_text,
            'options': question.options,
            'order': sq.order_number
        }

    def submit_answer(self, session_id: int, question_id: int, user_answer: str, time_taken: int) -> Dict:
        """
        Process a user's answer submission.
        """
        try:
            session = self.db.query(QuizSession).get(session_id)
            if not session or session.is_completed:
                return {'status': 'error', 'message': 'Invalid or completed session.'}

            question = self.db.query(Question).get(question_id)
            if not question:
                raise ValueError(f"Question with id {question_id} not found.")

            is_correct = False
            if user_answer is not None and question.correct_answer is not None:
                is_correct = user_answer.strip().lower() == question.correct_answer.strip().lower()

            # Update QuizSessionQuestion
            self.db.query(QuizSessionQuestion).filter(
                QuizSessionQuestion.session_id == session_id,
                QuizSessionQuestion.question_id == question_id
            ).update({
                'is_answered': True,
                'user_answer': user_answer,
                'is_correct': is_correct,
                'time_taken': time_taken,
                'answered_at': datetime.now(timezone.utc)
            })

            # Update UserAnswer history
            self._update_user_answer_history(session.user_id, question_id, is_correct, time_taken)

            # Update global question stats
            if question.total_attempts is None: question.total_attempts = 0
            if question.total_incorrect is None: question.total_incorrect = 0
            question.total_attempts += 1
            if not is_correct:
                question.total_incorrect += 1

            # Log interaction
            self._log_interaction(session, question_id, is_correct, time_taken)
            
            # Update global question stats
            if question.total_attempts is None: question.total_attempts = 0
            if question.total_incorrect is None: question.total_incorrect = 0
            question.total_attempts += 1
            if not is_correct:
                question.total_incorrect += 1

            # Log interaction
            self._log_interaction(session, question_id, is_correct, time_taken)

            # Check for quiz completion
            next_question = self.get_next_question(session_id)
            quiz_completed = next_question is None
            
            if quiz_completed:
                self._complete_session(session_id)

            self.db.commit()

            return {
                'status': 'success',
                'is_correct': is_correct,
                'correct_answer': question.correct_answer,
                'explanation': question.explanation,
                'next_question': next_question,
                'quiz_completed': quiz_completed
            }

        except Exception as e:
            self.db.rollback()
            logging.exception(f"Failed to submit answer for session {session_id}")
            return {'status': 'error', 'message': f'An unexpected error occurred while submitting your answer.'}

    def _update_user_answer_history(self, user_id: int, question_id: int, is_correct: bool, time_taken: int):
        # Find the latest answer for this user/question
        latest_answer = self.db.query(UserAnswer).filter(
            UserAnswer.user_id == user_id,
            UserAnswer.question_id == question_id
        ).order_by(UserAnswer.timestamp.desc()).first()

        last_streak = 0
        if latest_answer and latest_answer.correct_streak is not None:
            last_streak = latest_answer.correct_streak
        
        new_streak = (last_streak + 1) if is_correct else 0
        
        new_answer = UserAnswer(
            user_id=user_id,
            question_id=question_id,
            is_correct=is_correct,
            time_taken=time_taken,
            correct_streak=new_streak,
            next_review_date=self.db_selector.selector.calculate_next_review_date(new_streak) if is_correct else None
        )
        self.db.add(new_answer)

    def _log_interaction(self, session: QuizSession, question_id: int, is_correct: bool, time_taken: int):
        sq = self.db.query(QuizSessionQuestion).filter(
            QuizSessionQuestion.session_id == session.id,
            QuizSessionQuestion.question_id == question_id
        ).first()

        # NOTE: The count() here is subject to a race condition. Two concurrent answers
        # for the same question from the same user could get the same attempt_number.
        # This is best solved with a database lock or trigger.
        attempt_count = self.db.query(InteractionLog).filter(
            InteractionLog.user_id == session.user_id,
            InteractionLog.question_id == question_id
        ).count()

        log = InteractionLog(
            user_id=session.user_id,
            question_id=question_id,
            session_id=session.id,
            is_correct=is_correct,
            time_taken=time_taken,
            attempt_number=attempt_count + 1,
            was_weakness=(sq.selection_reason == SelectionReason.WEAKNESS.value if sq else False),
            was_srs=(sq.selection_reason == SelectionReason.SRS_DUE.value if sq else False),
            was_new=(sq.selection_reason == SelectionReason.NEW_QUESTION.value if sq else False),
            is_first_attempt=(attempt_count == 0)
        )
        self.db.add(log)

    def _complete_session(self, session_id: int):
        session = self.db.query(QuizSession).get(session_id)
        if not session: return

        session.is_completed = True
        session.completed_at = datetime.now(timezone.utc)

        correct_count = self.db.query(QuizSessionQuestion).filter(
            QuizSessionQuestion.session_id == session_id,
            QuizSessionQuestion.is_correct == True
        ).count()
        
        if session.total_questions and session.total_questions > 0:
            session.final_score = (correct_count / session.total_questions * 100)
        else:
            session.final_score = 0