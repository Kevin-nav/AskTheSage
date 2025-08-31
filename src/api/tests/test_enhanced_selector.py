# src/api/tests/test_enhanced_selector.py

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.models.models import User, Course, Level, Question, UserAnswer, QuizSession
from src.adaptive_learning.selector import UniversalQuestionSelector, UserPerformance, SelectionReason

# --- Fixtures ---

@pytest.fixture
def selector_config():
    """Provides a standard config for the selector."""
    return {
        'target_weakness_pct': 0.5,
        'target_new_pct': 0.3,
        'target_srs_pct': 0.1,
        'target_progression_pct': 0.1,
    }

@pytest.fixture
def setup_course_and_user(db: Session):
    """Fixture to create a standard user, level, and course."""
    user = User(telegram_id=12345, username="testuser")
    level = Level(name="100")
    course = Course(name="Calculus", level=level, min_difficulty=3.0, max_difficulty=5.0)
    db.add_all([user, level, course])
    db.commit()
    return user, course

# --- Test Cases ---

def test_guided_placement_for_new_user(db: Session, setup_course_and_user, selector_config):
    """
    Tests that a new user gets a quiz ramped by relative difficulty.
    """
    # Arrange
    user, course = setup_course_and_user
    selector = UniversalQuestionSelector(selector_config)
    
    questions = {
        1: {'difficulty_score': 3.0}, # Relative: 0.0
        2: {'difficulty_score': 3.2}, # Relative: 0.1
        3: {'difficulty_score': 4.0}, # Relative: 0.5
        4: {'difficulty_score': 4.8}, # Relative: 0.9
    }

    # Act
    # Since it's a new user, the user_performance list is empty.
    # The selector will treat all questions as "new" and score them based on appropriateness.
    selected_questions = selector.select_questions([], questions, (3.0, 5.0), 4)
    
    # Assert
    # The selector should prioritize questions closer to the starting skill level (0.25)
    selected_ids = [q.question_id for q in selected_questions]
    # The two easiest questions should be selected first, in some order.
    assert set(selected_ids[:2]) == {1, 2}
    # The two hardest questions should be selected last, in some order.
    assert set(selected_ids[2:]) == {3, 4}

def test_personalization_overrides_difficulty(db: Session, setup_course_and_user, selector_config):
    """
    Tests that a user's weakness is prioritized over difficulty progression.
    """
    # Arrange
    user, course = setup_course_and_user
    selector = UniversalQuestionSelector(selector_config)
    
    questions = {
        1: {'difficulty_score': 3.0}, # Weakness (easy)
        2: {'difficulty_score': 4.0}, # Strong (medium)
        3: {'difficulty_score': 4.5}, # Progression (hard)
    }
    
    user_performance = [
        UserPerformance(question_id=1, correct_streak=0, last_attempt_correct=False, last_attempt_date=datetime.now(), total_attempts=1, total_correct=0, difficulty_score=3.0),
        UserPerformance(question_id=2, correct_streak=2, last_attempt_correct=True, last_attempt_date=datetime.now(), total_attempts=2, total_correct=2, difficulty_score=4.0, next_review_date=datetime.now() + timedelta(days=5)),
    ]

    # Act
    selected_questions = selector.select_questions(user_performance, questions, (3.0, 5.0), 2)
    
    # Assert
    reasons = [q.reason for q in selected_questions]
    assert SelectionReason.WEAKNESS in reasons
    # The other question should be a progression or new question, but weakness is key.
    assert selected_questions[0].reason == SelectionReason.WEAKNESS

def test_relative_difficulty_across_courses(db: Session, setup_course_and_user, selector_config):
    """
    Tests that the selector correctly uses relative difficulty.
    """
    # Arrange
    user, course = setup_course_and_user # This is the "hard" course
    selector = UniversalQuestionSelector(selector_config)
    
    # A "hard" question in the hard course
    hard_course_questions = {1: {'difficulty_score': 4.8}} # Relative: 0.9
    
    # An "easy" course
    easy_course = Course(name="French", level_id=course.level_id, min_difficulty=1.0, max_difficulty=2.5)
    db.add(easy_course)
    db.commit()
    
    # A "hard" question in the easy course
    easy_course_questions = {2: {'difficulty_score': 2.4}} # Relative: 0.93

    # Act
    # The user has no history, so both are "new" questions.
    # The score will be based on appropriateness to the starting skill level (0.25)
    hard_course_selection = selector.select_questions([], hard_course_questions, (3.0, 5.0), 1)
    easy_course_selection = selector.select_questions([], easy_course_questions, (1.0, 2.5), 1)

    # Assert
    # The logic for new questions is to score them based on how close they are to the
    # starting skill level. A very hard question (relative score ~0.9) will get a low
    # appropriateness bonus.
    assert hard_course_selection[0].score < 80 # Should be penalized for being too hard
    assert easy_course_selection[0].score < 80
    # The scores should be similar because their relative difficulties are similar
    assert abs(hard_course_selection[0].score - easy_course_selection[0].score) < 10