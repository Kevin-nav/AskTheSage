
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.models import User, Course, QuizSession, InteractionLog, Question, Level, Faculty, Program

def test_get_dashboard_stats(authenticated_client: TestClient, db: Session):
    # Arrange
    # The authenticated_client fixture creates one admin user.
    user1 = User(telegram_id=1, username="user1")
    user2 = User(telegram_id=2, username="user2")
    db.add_all([user1, user2])
    db.commit()

    level = Level(name="100")
    db.add(level)
    db.commit()

    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()

    question = Question(question_text="Test", options=[], correct_answer="A", course_id=course.id)
    db.add(question)
    db.commit()

    # 3 sessions, 2 completed -> 66.7% completion
    session1 = QuizSession(user_id=user1.id, course_id=course.id, total_questions=1, is_completed=True)
    session2 = QuizSession(user_id=user1.id, course_id=course.id, total_questions=1, is_completed=True)
    session3 = QuizSession(user_id=user2.id, course_id=course.id, total_questions=1, is_completed=False)
    db.add_all([session1, session2, session3])
    db.commit()

    # 2 interactions, total time = 1800 + 1800 = 3600s = 1.0 hours
    log1 = InteractionLog(user_id=user1.id, question_id=question.id, session_id=session1.id, is_correct=True, time_taken=1800, attempt_number=1)
    log2 = InteractionLog(user_id=user2.id, question_id=question.id, session_id=session2.id, is_correct=False, time_taken=1800, attempt_number=1)
    db.add_all([log1, log2])
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/dashboard/stats")

    # Assert
    assert response.status_code == 200
    data = response.json()
    
    stats_dict = {item['title']: item for item in data}
    
    assert stats_dict["Total Students"]["value"] == "3" # Includes admin user
    assert stats_dict["Bot Interactions"]["value"] == "2"
    assert stats_dict["Course Completion"]["value"] == "66.7%"
    assert stats_dict["Learning Hours"]["value"] == "1.00"

def test_get_recent_activity(authenticated_client: TestClient, db: Session):
    # Arrange
    user = db.query(User).filter(User.username == "testadmin").first()
    faculty = Faculty(name="Admin Faculty")
    program = Program(name="Admin Program", faculty=faculty)
    level = Level(name="Admin Level")
    db.add_all([faculty, program, level])
    db.commit()

    course = Course(name="Admin Course", level_id=level.id)
    db.add(course)
    db.commit()

    question = Question(question_text="Is this a test?", options=["Yes", "No"], correct_answer="Yes", course_id=course.id)
    db.add(question)
    db.commit()

    session = QuizSession(user_id=user.id, course_id=course.id, started_at=datetime.now(), total_questions=1)
    db.add(session)
    db.commit()

    log = InteractionLog(user_id=user.id, question_id=question.id, session_id=session.id, timestamp=datetime.now(), is_correct=True, time_taken=10, attempt_number=1)
    db.add(log)
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/dashboard/recent-activity")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    
    actions = {item['action'] for item in data}
    assert f"started {course.name}" in actions
    assert f"answered a question in {course.name}" in actions
