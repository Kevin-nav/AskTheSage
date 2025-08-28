
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.models.models import User, Question, Course, Level, QuestionReport, QuizSession

def test_create_report(authenticated_client: TestClient, db: Session):
    # Arrange
    user = db.query(User).filter(User.username == "testadmin").first()
    level = Level(name="100")
    db.add(level)
    db.commit()
    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()
    question = Question(question_text="Test Question", options=["A"], correct_answer="A", course_id=course.id)
    db.add(question)
    db.commit()

    report_data = {
        "question_id": question.id,
        "reason": "This question is unclear."
    }

    # Act
    response = authenticated_client.post(
        "/api/v1/reports",
        json=report_data,
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["question_id"] == question.id
    assert data["user_id"] == user.id
    assert data["reason"] == "This question is unclear."
    assert data["status"] == "open"

def test_create_report_non_existent_question(authenticated_client: TestClient, db: Session):
    # Arrange
    report_data = {
        "question_id": 99999, # Non-existent ID
        "reason": "Question does not exist."
    }

    # Act
    response = authenticated_client.post(
        "/api/v1/reports",
        json=report_data,
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Question not found"

def test_get_all_reports(authenticated_client: TestClient, db: Session):
    # Arrange
    user = db.query(User).filter(User.username == "testadmin").first()
    level = Level(name="100")
    db.add(level)
    db.commit()
    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()
    question1 = Question(question_text="Q1", options=["A"], correct_answer="A", course_id=course.id)
    question2 = Question(question_text="Q2", options=["B"], correct_answer="B", course_id=course.id)
    db.add_all([question1, question2])
    db.commit()

    report1 = QuestionReport(question_id=question1.id, user_id=user.id, reason="R1", status="open", reported_at=datetime.now() - timedelta(days=1))
    report2 = QuestionReport(question_id=question2.id, user_id=user.id, reason="R2", status="closed", reported_at=datetime.now() - timedelta(days=2))
    report3 = QuestionReport(question_id=question1.id, user_id=user.id, reason="R3", status="open", reported_at=datetime.now())
    db.add_all([report1, report2, report3])
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/reports")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # Check sorting (newest first)
    assert data["items"][0]["reason"] == "R3"
    assert data["items"][0]["question_text"] == "Q1"
    assert data["items"][0]["course_name"] == "Test Course"

def test_get_all_reports_filter_status(authenticated_client: TestClient, db: Session):
    # Arrange (same as test_get_all_reports)
    user = db.query(User).filter(User.username == "testadmin").first()
    level = Level(name="100")
    db.add(level)
    db.commit()
    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()
    question1 = Question(question_text="Q1", options=["A"], correct_answer="A", course_id=course.id)
    question2 = Question(question_text="Q2", options=["B"], correct_answer="B", course_id=course.id)
    db.add_all([question1, question2])
    db.commit()

    report1 = QuestionReport(question_id=question1.id, user_id=user.id, reason="R1", status="open")
    report2 = QuestionReport(question_id=question2.id, user_id=user.id, reason="R2", status="closed")
    report3 = QuestionReport(question_id=question1.id, user_id=user.id, reason="R3", status="open")
    db.add_all([report1, report2, report3])
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/reports?status_filter=open")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert all(r["status"] == "open" for r in data["items"])

def test_get_report_stats(authenticated_client: TestClient, db: Session):
    # Arrange
    user = db.query(User).filter(User.username == "testadmin").first()
    level = Level(name="100")
    db.add(level)
    db.commit()
    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()
    question1 = Question(question_text="Q1", options=["A"], correct_answer="A", course_id=course.id)
    question2 = Question(question_text="Q2", options=["B"], correct_answer="B", course_id=course.id)
    question3 = Question(question_text="Q3", options=["C"], correct_answer="C", course_id=course.id)
    db.add_all([question1, question2, question3])
    db.commit()

    # Reports: Q1 (2 open), Q2 (1 closed), Q3 (1 open)
    report1 = QuestionReport(question_id=question1.id, user_id=user.id, reason="R1", status="open")
    report2 = QuestionReport(question_id=question2.id, user_id=user.id, reason="R2", status="closed")
    report3 = QuestionReport(question_id=question1.id, user_id=user.id, reason="R3", status="open")
    report4 = QuestionReport(question_id=question3.id, user_id=user.id, reason="R4", status="open")
    db.add_all([report1, report2, report3, report4])
    db.commit()

    # Act
    response = authenticated_client.get("/api/v1/admin/reports/stats")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total_reports"] == 4
    assert data["open_reports"] == 3
    assert data["closed_reports"] == 1

    most_reported = data["most_reported_questions"]
    assert len(most_reported) > 0
    assert most_reported[0]["question_id"] == question1.id
    assert most_reported[0]["report_count"] == 2

def test_get_report_by_id(authenticated_client: TestClient, db: Session):
    # Arrange
    user = db.query(User).filter(User.username == "testadmin").first()
    level = Level(name="100")
    db.add(level)
    db.commit()
    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()
    question = Question(question_text="A specific question", options=["A"], correct_answer="A", course_id=course.id)
    db.add(question)
    db.commit()
    report = QuestionReport(question_id=question.id, user_id=user.id, reason="A specific reason", status="open")
    db.add(report)
    db.commit()

    # Act
    response = authenticated_client.get(f"/api/v1/admin/reports/{report.id}")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == report.id
    assert data["reason"] == "A specific reason"
    assert data["question_text"] == "A specific question"
    assert data["course_name"] == "Test Course"

def test_update_report_status(authenticated_client: TestClient, db: Session):
    # Arrange
    user = db.query(User).filter(User.username == "testadmin").first()
    level = Level(name="100")
    db.add(level)
    db.commit()
    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()
    question = Question(question_text="Q1", options=["A"], correct_answer="A", course_id=course.id)
    db.add(question)
    db.commit()
    report = QuestionReport(question_id=question.id, user_id=user.id, reason="R1", status="open")
    db.add(report)
    db.commit()

    update_data = {"status": "closed"}

    # Act
    response = authenticated_client.patch(f"/api/v1/admin/reports/{report.id}", json=update_data)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"
    
    db.refresh(report)
    assert report.status == "closed"

def test_update_report_status_invalid_status(authenticated_client: TestClient, db: Session):
    # Arrange
    user = db.query(User).filter(User.username == "testadmin").first()
    level = Level(name="100")
    db.add(level)
    db.commit()
    course = Course(name="Test Course", level_id=level.id)
    db.add(course)
    db.commit()
    question = Question(question_text="Q1", options=["A"], correct_answer="A", course_id=course.id)
    db.add(question)
    db.commit()
    report = QuestionReport(question_id=question.id, user_id=user.id, reason="R1", status="open")
    db.add(report)
    db.commit()

    update_data = {"status": "some_invalid_status"}

    # Act
    response = authenticated_client.patch(f"/api/v1/admin/reports/{report.id}", json=update_data)

    # Assert
    assert response.status_code == 400
