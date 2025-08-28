
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta

from src.api.dependencies import get_db
from src.api.schemas import CourseStats, CourseDetail, CoursePage
from src.models.models import Course, QuizSession, Question, Level, User

from src.api.routers.auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/courses",
    tags=["Admin Courses"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/stats", response_model=CourseStats)
async def get_course_stats(db: Session = Depends(get_db)):
    total_courses = db.query(Course).count()

    # Active courses are those with quiz sessions in the last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    active_courses = db.query(Course.id).join(QuizSession).filter(QuizSession.started_at >= thirty_days_ago).distinct().count()

    # Placeholders
    total_enrollment = db.query(QuizSession.user_id).distinct().count()
    total_sessions = db.query(QuizSession).count()
    completed_sessions = db.query(QuizSession).filter(QuizSession.is_completed == True).count()
    avg_completion_rate = (completed_sessions / total_sessions) * 100 if total_sessions > 0 else 0

    return CourseStats(
        total_courses=total_courses,
        active_courses=active_courses,
        total_enrollment=total_enrollment,
        avg_completion_rate=avg_completion_rate
    )

@router.get("", response_model=CoursePage)
async def get_courses(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    sort_by: str = Query("id", description="Field to sort by"),
    sort_dir: str = Query("asc", description="Sort direction (asc/desc)"),
):
    # Subquery for enrolled students
    enrolled_sq = db.query(
        QuizSession.course_id,
        func.count(func.distinct(QuizSession.user_id)).label("students_enrolled")
    ).group_by(QuizSession.course_id).subquery()

    # Subquery for question stats
    question_sq = db.query(
        Question.course_id,
        func.count(Question.id).label("total_questions"),
        func.avg(Question.difficulty_score).label("avg_difficulty")
    ).group_by(Question.course_id).subquery()

    # Main query
    query = db.query(
        Course.id,
        Course.name,
        Level.name.label("level_name"),
        func.coalesce(enrolled_sq.c.students_enrolled, 0).label("students_enrolled"),
        func.coalesce(question_sq.c.total_questions, 0).label("total_questions"),
        func.coalesce(question_sq.c.avg_difficulty, 0.0).label("avg_difficulty")
    ).join(Level, Course.level_id == Level.id).outerjoin(enrolled_sq, Course.id == enrolled_sq.c.course_id).outerjoin(question_sq, Course.id == question_sq.c.course_id)

    # Sorting
    if hasattr(Course, sort_by):
        sort_col = getattr(Course, sort_by)
        if sort_dir == "desc":
            sort_col = sort_col.desc()
        query = query.order_by(sort_col)

    # Pagination
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    course_details = [
        CourseDetail(
            id=item.id,
            name=item.name,
            level=item.level_name,
            students_enrolled=item.students_enrolled,
            total_questions=item.total_questions,
            avg_difficulty=float(item.avg_difficulty)
        ) for item in items
    ]

    return CoursePage(
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
        items=course_details
    )
