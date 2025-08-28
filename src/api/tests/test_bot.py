
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.models import InteractionLog, User, Question, Course, Level, QuizSession


def test_get_bot_interactions(authenticated_client: TestClient, db: Session):
    # Arrange
    user = User(telegram_id=1, full_name="Test User")
    level = Level(name="100")
    db.add_all([user, level])
    db.commit()

    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()

    question = Question(course_id=course.id, question_text="What is FastAPI?", options=["A", "B"], correct_answer="A")
    db.add(question)
    db.commit()

    session = QuizSession(user_id=user.id, course_id=course.id, total_questions=1)
    db.add(session)
    db.commit()

    # Create some interaction logs
    for i in range(15):
        log = InteractionLog(
            user_id=user.id,
            question_id=question.id,
            session_id=session.id,
            is_correct= (i % 2 == 0),
            time_taken=10 + i,
            timestamp=datetime.now(),
            attempt_number=1
        )
        db.add(log)
    db.commit()

    # Act: Get first page
    response = authenticated_client.get("/api/v1/admin/bot/interactions?page=1&size=10")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["size"] == 10
    assert len(data["items"]) == 10

    item = data["items"][0]
    assert item["user_name"] == "Test User"
    assert item["question_text"] == "What is FastAPI?"
    assert item["course_name"] == "Test Course"
    assert "is_correct" in item
    assert "time_taken" in item

    # Act: Get second page
    response = authenticated_client.get("/api/v1/admin/bot/interactions?page=2&size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5

def test_get_bot_stats(authenticated_client: TestClient, db: Session):
    # Arrange
    user = User(telegram_id=2, full_name="Stats User")
    level = Level(name="200")
    db.add_all([user, level])
    db.commit()

    course = Course(name="Stats Course", level_id=level.id)
    db.add(course)
    db.commit()

    question = Question(course_id=course.id, question_text="Question for stats?", options=["A"], correct_answer="A")
    db.add(question)
    db.commit()

    session = QuizSession(user_id=user.id, course_id=course.id, total_questions=4)
    db.add(session)
    db.commit()

    # Add interactions
    db.add(InteractionLog(user_id=user.id, question_id=question.id, session_id=session.id, is_correct=True, time_taken=10, attempt_number=1))
    db.add(InteractionLog(user_id=user.id, question_id=question.id, session_id=session.id, is_correct=True, time_taken=20, attempt_number=1))
    db.add(InteractionLog(user_id=user.id, question_id=question.id, session_id=session.id, is_correct=False, time_taken=15, attempt_number=1))
    db.add(InteractionLog(user_id=user.id, question_id=question.id, session_id=session.id, is_correct=False, time_taken=25, attempt_number=1))
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/bot/stats")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["avg_response_time"] == 17.5 # (10 + 20 + 15 + 25) / 4
    assert data["accuracy_rate"] == 50.0 # 2 correct out of 4
