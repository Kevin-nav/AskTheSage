from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from src.api.dependencies import get_db
from src.api.schemas import PublicStats, PublicRecentActivityItem
from src.models.models import User, InteractionLog, QuizSession, Course

router = APIRouter(
    prefix="/api/v1/public",
    tags=["Public"],
)

@router.get("/stats", response_model=PublicStats)
async def get_public_stats(db: Session = Depends(get_db)):
    total_students = db.query(User).count()
    total_interactions = db.query(InteractionLog).count()

    # For active_courses, we'll define it as courses with at least one completed quiz session in the last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    active_courses_count = db.query(Course.id).join(QuizSession).filter(QuizSession.completed_at >= thirty_days_ago).distinct().count()

    # Placeholder for completion_rate_percent, avg_session_minutes, success_rate_percent (Category 2)
    completion_rate_percent = 0.0
    avg_session_minutes = 0
    success_rate_percent = 0.0

    return PublicStats(
        total_students=total_students,
        active_courses=active_courses_count,
        completion_rate_percent=completion_rate_percent, # Placeholder
        avg_session_minutes=avg_session_minutes,         # Placeholder
        total_interactions=total_interactions,
        success_rate_percent=success_rate_percent        # Placeholder
    )

@router.get("/recent-activity", response_model=List[PublicRecentActivityItem])
async def get_public_recent_activity(db: Session = Depends(get_db)):
    # For public recent activity, we'll show courses with recent quiz sessions
    # and a placeholder for active students and trend.
    recent_quiz_sessions = db.query(QuizSession).order_by(QuizSession.started_at.desc()).limit(5).all()

    activity_items = []
    processed_course_ids = set()

    for session in recent_quiz_sessions:
        if session.course_id not in processed_course_ids:
            course = db.query(Course).filter(Course.id == session.course_id).first()
            if course:
                # Placeholder values for active_students and trend_percent
                activity_items.append(PublicRecentActivityItem(
                    course_name=course.name,
                    active_students=0, # Placeholder
                    trend_percent="+0%" # Placeholder
                ))
                processed_course_ids.add(session.course_id)

    return activity_items[:5] # Return top 5 unique courses with recent activity
