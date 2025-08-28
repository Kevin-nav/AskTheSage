
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.models.models import Course, Level, Question, QuizSession, User

def test_get_course_stats(authenticated_client: TestClient, db: Session):
    # Arrange
    level = Level(name="100")
    db.add(level)
    db.commit()

    course1 = Course(name="Active Course", level_id=level.id)
    course2 = Course(name="Inactive Course", level_id=level.id)
    db.add_all([course1, course2])
    db.commit()

    user1 = User(telegram_id=1)
    user2 = User(telegram_id=2)
    db.add_all([user1, user2])
    db.commit()

    # Session for active course (completed)
    session1 = QuizSession(user_id=user1.id, course_id=course1.id, started_at=datetime.now(), total_questions=1, is_completed=True)
    # Session for active course (incomplete)
    session2 = QuizSession(user_id=user2.id, course_id=course1.id, started_at=datetime.now(), total_questions=1, is_completed=False)
    db.add_all([session1, session2])
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/courses/stats")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total_courses"] == 2
    assert data["active_courses"] == 1
    assert data["total_enrollment"] == 2
    assert data["avg_completion_rate"] == 50.0

def test_get_courses_paginated(authenticated_client: TestClient, db: Session):
    # Arrange
    level = Level(name="200")
    db.add(level)
    db.commit()

    for i in range(15):
        db.add(Course(name=f"Course {i}", level_id=level.id))
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/courses?page=1&size=10")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["size"] == 10
    assert len(data["items"]) == 10

def test_get_course_details(authenticated_client: TestClient, db: Session):
    # Arrange
    level = Level(name="300")
    db.add(level)
    db.commit()

    course = Course(name="Detailed Course", level_id=level.id)
    db.add(course)
    db.commit()

    # Add questions with difficulty
    q1 = Question(course_id=course.id, question_text="q1", options=[], correct_answer="A", difficulty_score=2.5)
    q2 = Question(course_id=course.id, question_text="q2", options=[], correct_answer="B", difficulty_score=3.5)
    db.add_all([q1, q2])

    # Add enrolled users
    user1 = User(telegram_id=101)
    user2 = User(telegram_id=102)
    db.add_all([user1, user2])
    db.commit()

    s1 = QuizSession(user_id=user1.id, course_id=course.id, total_questions=2)
    s2 = QuizSession(user_id=user2.id, course_id=course.id, total_questions=2)
    db.add_all([s1, s2])
    db.commit()

    # Act
    response = authenticated_client.get(f"/api/v1/admin/courses")

    # Assert
    assert response.status_code == 200
    data = response.json()
    
    course_item = None
    for item in data['items']:
        if item['id'] == course.id:
            course_item = item
            break

    assert course_item is not None
    assert course_item["name"] == "Detailed Course"
    assert course_item["level"] == "300"
    assert course_item["students_enrolled"] == 2
    assert course_item["total_questions"] == 2
    assert course_item["avg_difficulty"] == 3.0
