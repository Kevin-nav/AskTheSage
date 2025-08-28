
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, case
from typing import List
from datetime import datetime, timedelta, timezone

from src.api.dependencies import get_db
from src.api.schemas import StudentStats, StudentDetail, StudentPage
from src.models.models import User, InteractionLog, QuizSession, Course
# from src.api.routers.auth import get_current_admin_user # TODO: Add admin authentication

from src.api.routers.auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/students",
    tags=["Admin Students"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/stats", response_model=StudentStats)
async def get_student_stats(db: Session = Depends(get_db)):
    total_students = db.query(User).count()

    # Define "active" as having an interaction in the last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_students = db.query(User.id).join(InteractionLog).filter(InteractionLog.timestamp >= thirty_days_ago).distinct().count()

    # Placeholders for more complex stats
    total_sessions = db.query(QuizSession).count()
    completed_sessions = db.query(QuizSession).filter(QuizSession.is_completed == True).count()
    completion_rate = (completed_sessions / total_sessions) * 100 if total_sessions > 0 else 0

    avg_gpa = 0.0 # Placeholder

    return StudentStats(
        total_students=total_students,
        active_students=active_students,
        completion_rate=completion_rate,
        avg_gpa=avg_gpa # Placeholder
    )

@router.get("", response_model=StudentPage)
async def get_students(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    sort_by: str = Query("id", description="Field to sort by"),
    sort_dir: str = Query("asc", description="Sort direction (asc/desc)"),
):
    # Subquery for last active date
    last_active_sq = db.query(
        InteractionLog.user_id,
        func.max(InteractionLog.timestamp).label("last_active")
    ).group_by(InteractionLog.user_id).subquery()

    # Subquery for quiz stats
    quiz_stats_sq = db.query(
        QuizSession.user_id,
        func.count(QuizSession.id).label("total_quizzes"),
        func.avg(QuizSession.final_score).label("avg_score"),
        func.count(func.distinct(QuizSession.course_id)).label("courses_taken")
    ).group_by(QuizSession.user_id).subquery()

    # Main query
    query = db.query(
        User.id,
        User.full_name,
        User.username,
        User.email,
        last_active_sq.c.last_active,
        func.coalesce(quiz_stats_sq.c.total_quizzes, 0).label("total_quizzes"),
        func.coalesce(quiz_stats_sq.c.avg_score, 0.0).label("avg_score"),
        func.coalesce(quiz_stats_sq.c.courses_taken, 0).label("courses_taken")
    ).outerjoin(last_active_sq, User.id == last_active_sq.c.user_id).outerjoin(quiz_stats_sq, User.id == quiz_stats_sq.c.user_id)

    # Sorting
    if hasattr(User, sort_by):
        sort_col = getattr(User, sort_by)
        if sort_dir == "desc":
            sort_col = sort_col.desc()
        query = query.order_by(sort_col)

    # Pagination
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    student_details = [
        StudentDetail(
            id=item.id,
            name=item.full_name or item.username or f"User {item.id}",
            email=item.email,
            last_active=item.last_active,
            status="Active" if item.last_active and item.last_active > (datetime.now(timezone.utc) - timedelta(days=30)) else "Inactive",
            courses_taken=item.courses_taken,
            total_quizzes=item.total_quizzes,
            avg_score=float(item.avg_score)
        ) for item in items
    ]

    return StudentPage(
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
        items=student_details
    )
