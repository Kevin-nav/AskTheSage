from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.models.models import User, Course, QuizSession, InteractionLog, Level, Faculty, Program, Question

def test_get_public_stats(client: TestClient, db: Session):
    # Arrange: Add some data to the test database
    user1 = User(telegram_id=1)
    user2 = User(telegram_id=2)
    db.add_all([user1, user2])
    db.commit()

    faculty = Faculty(name="Test Faculty")
    program = Program(name="Test Program", faculty=faculty)
    level = Level(name="100")
    db.add_all([faculty, program, level])
    db.commit()

    course1 = Course(name="Course 1", level_id=level.id)
    db.add(course1)
    db.commit()

    question = Question(question_text="Sample Question", options=["A", "B"], correct_answer="A", course_id=course1.id)
    db.add(question)
    db.commit()

    # Active course session
    active_session = QuizSession(user_id=user1.id, course_id=course1.id, started_at=datetime.now(), completed_at=datetime.now(), is_completed=True, total_questions=10)
    db.add(active_session)
    db.commit()

    db.add(InteractionLog(user_id=user1.id, question_id=question.id, session_id=active_session.id, time_taken=10, is_correct=True, attempt_number=1))
    db.add(InteractionLog(user_id=user2.id, question_id=question.id, session_id=active_session.id, time_taken=15, is_correct=False, attempt_number=1))
    db.commit()

    # Act
    response = client.get("/api/v1/public/stats")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] == 2
    assert data["active_courses"] == 1
    assert data["total_interactions"] == 2

def test_get_public_recent_activity(client: TestClient, db: Session):
    # Arrange
    user1 = User(telegram_id=1)
    user2 = User(telegram_id=2)
    db.add_all([user1, user2])
    db.commit()

    level = Level(name="200")
    db.add(level)
    db.commit()

    course1 = Course(name="Intro to Testing", level_id=level.id)
    course2 = Course(name="Advanced FastAPI", level_id=level.id)
    db.add_all([course1, course2])
    db.commit()

    session1 = QuizSession(user_id=user1.id, course_id=course1.id, started_at=datetime.now() - timedelta(days=1), total_questions=5)
    session2 = QuizSession(user_id=user2.id, course_id=course2.id, started_at=datetime.now(), total_questions=5)
    db.add_all([session1, session2])
    db.commit()

    # Act
    response = client.get("/api/v1/public/recent-activity")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 5
    assert data[0]["course_name"] == "Advanced FastAPI"
    assert data[1]["course_name"] == "Intro to Testing"