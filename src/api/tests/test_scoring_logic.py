# src/api/tests/test_scoring_logic.py

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.models.models import User, Course, Level, QuizSession, QuizSessionQuestion
from src.services.quiz_service import cancel_quiz_session, get_user_performance_data

# --- Fixtures ---

@pytest.fixture
def setup_course_and_user(db: Session):
    """Fixture to create a standard user, level, and course."""
    user = User(telegram_id=12345, username="testuser")
    level = Level(name="100")
    course = Course(name="Test Course", level=level)
    db.add_all([user, level, course])
    db.commit()
    return user, course

# --- Test Cases ---

def test_cancel_untouched_quiz(db: Session, setup_course_and_user):
    """
    Tests that cancelling a quiz with ZERO answered questions deletes the session.
    """
    # Arrange
    user, course = setup_course_and_user
    session = QuizSession(user_id=user.id, course_id=course.id, total_questions=10, status='in_progress')
    db.add(session)
    db.commit()
    session_id = session.id

    # Act
    result = cancel_quiz_session(db, session_id)

    # Assert
    assert result == "DELETED"
    deleted_session = db.query(QuizSession).filter_by(id=session_id).first()
    assert deleted_session is None

def test_cancel_touched_quiz(db: Session, setup_course_and_user):
    """
    Tests that cancelling a quiz with answered questions scores it fairly.
    """
    # Arrange
    user, course = setup_course_and_user
    session = QuizSession(user_id=user.id, course_id=course.id, total_questions=10, status='in_progress')
    db.add(session)
    db.commit()
    
    # Simulate one correct and one incorrect answer
    q1 = QuizSessionQuestion(session_id=session.id, question_id=1, order_number=1, is_answered=True, is_correct=True)
    q2 = QuizSessionQuestion(session_id=session.id, question_id=2, order_number=2, is_answered=True, is_correct=False)
    db.add_all([q1, q2])
    db.commit()
    session_id = session.id

    # Act
    result = cancel_quiz_session(db, session_id)

    # Assert
    assert result == "SCORED"
    updated_session = db.query(QuizSession).filter_by(id=session_id).first()
    assert updated_session is not None
    assert updated_session.status == 'cancelled'
    assert updated_session.final_score == 50.0 # 1 correct out of 2 answered

def test_performance_command_includes_all_statuses(db: Session, setup_course_and_user):
    """
    Tests that the performance data includes quizzes of all relevant statuses.
    """
    # Arrange
    user, course = setup_course_and_user
    now = datetime.now()
    
    # Create sessions with different statuses and scores
    s1 = QuizSession(user_id=user.id, course_id=course.id, total_questions=2, status='completed', final_score=100.0, completed_at=now - timedelta(days=3))
    s2 = QuizSession(user_id=user.id, course_id=course.id, total_questions=4, status='incomplete', final_score=75.0, completed_at=now - timedelta(days=2))
    s3 = QuizSession(user_id=user.id, course_id=course.id, total_questions=4, status='cancelled', final_score=50.0, completed_at=now - timedelta(days=1))
    s4 = QuizSession(user_id=user.id, course_id=course.id, total_questions=2, status='in_progress', final_score=None) # Should be ignored
    db.add_all([s1, s2, s3, s4])
    db.commit()

    # Act
    performance_data = get_user_performance_data(db, user.telegram_id)

    # Assert
    assert performance_data["total_quizzes"] == 3
    # Average should be (100 + 75 + 50) / 3
    assert performance_data["overall_average_score"] == 75.0
