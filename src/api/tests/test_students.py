from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.models.models import User, InteractionLog, QuizSession, Course, Level, Question

def test_get_student_stats(authenticated_client: TestClient, db: Session):
    # Arrange
    # authenticated_client creates 1 admin user
    user1 = User(telegram_id=1, username='user1', full_name='Test User 1')
    user2 = User(telegram_id=2, username='user2', full_name='Test User 2') # Active
    user3 = User(telegram_id=3, username='user3', full_name='Test User 3') # Inactive
    db.add_all([user1, user2, user3])
    db.commit()

    level = Level(name="100")
    db.add(level)
    db.commit()

    course = Course(name="Active Course", level_id=level.id)
    db.add(course)
    db.commit()

    question = Question(question_text="Stats Question", options=["A"], correct_answer="A", course_id=course.id)
    db.add(question)
    db.commit()

    # Add some quiz sessions
    # 1 completed, 1 incomplete -> 50% completion
    session1 = QuizSession(user_id=user2.id, course_id=course.id, total_questions=1, is_completed=True)
    session2 = QuizSession(user_id=user3.id, course_id=course.id, total_questions=1, is_completed=False)
    db.add_all([session1, session2])
    db.commit()

    # Interaction for active user
    db.add(InteractionLog(user_id=user2.id, question_id=question.id, session_id=session1.id, timestamp=datetime.now(), is_correct=True, time_taken=10, attempt_number=1))
    # Interaction for inactive user (older than 30 days)
    db.add(InteractionLog(user_id=user3.id, question_id=question.id, session_id=session2.id, timestamp=datetime.now() - timedelta(days=31), is_correct=True, time_taken=10, attempt_number=1))
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/students/stats")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] == 4 # 3 test users + 1 admin
    assert data["active_students"] == 1 # Only user2
    assert data["completion_rate"] == 50.0
    assert data["avg_gpa"] == 0.0

def test_get_students_paginated(authenticated_client: TestClient, db: Session):
    # Arrange: Create a few users
    for i in range(15):
        db.add(User(telegram_id=i, username=f'user{i}', full_name=f'Test User {i}'))
    db.commit()

    # Act: Get the first page
    response = authenticated_client.get("/api/v1/admin/students?page=1&size=10")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 15
    assert data["page"] == 1
    assert data["size"] == 10
    assert len(data["items"]) == 10

    # Act: Get the second page
    response = authenticated_client.get("/api/v1/admin/students?page=2&size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 5

def test_get_student_details(authenticated_client: TestClient, db: Session):
    # Arrange
    user = User(telegram_id=99, username='detail_user', full_name='Detail User')
    db.add(user)
    db.commit()

    level = Level(name="200")
    db.add(level)
    db.commit()

    course1 = Course(name="Course A", level_id=level.id)
    course2 = Course(name="Course B", level_id=level.id)
    db.add_all([course1, course2])
    db.commit()

    question = Question(question_text="Detail Question", options=["A"], correct_answer="A", course_id=course1.id)
    db.add(question)
    db.commit()

    # Add quiz sessions for the user
    session1 = QuizSession(user_id=user.id, course_id=course1.id, total_questions=10, final_score=80.0, is_completed=True)
    session2 = QuizSession(user_id=user.id, course_id=course2.id, total_questions=10, final_score=90.0, is_completed=True)
    session3 = QuizSession(user_id=user.id, course_id=course2.id, total_questions=10, final_score=70.0, is_completed=True)
    db.add_all([session1, session2, session3])
    db.commit()

    # Add interaction log
    last_active_time = datetime.now() - timedelta(days=5)
    db.add(InteractionLog(user_id=user.id, question_id=question.id, session_id=session1.id, timestamp=last_active_time, is_correct=True, time_taken=5, attempt_number=1))
    db.commit()

    # Act
    response = authenticated_client.get(f"/api/v1/admin/students")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    
    student_item = None
    for item in data['items']:
        if item['id'] == user.id:
            student_item = item
            break
    
    assert student_item is not None
    assert student_item["name"] == "Detail User"
    assert student_item["status"] == "Active"
    assert student_item["courses_taken"] == 2
    assert student_item["total_quizzes"] == 3
    assert student_item["avg_score"] == 80.0
    assert datetime.fromisoformat(student_item["last_active"]).date() == last_active_time.date()