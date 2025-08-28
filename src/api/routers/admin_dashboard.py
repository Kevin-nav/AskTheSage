from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta, timezone # Added timezone
from sqlalchemy import func, case

from src.api.dependencies import get_db
from src.api.schemas import DashboardStat, RecentActivity, UserActivity
from src.models.models import User, InteractionLog, QuizSession, Course

from src.api.routers.auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/dashboard",
    tags=["Admin Dashboard"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/stats", response_model=List[DashboardStat])
async def get_dashboard_stats(db: Session = Depends(get_db)):
    total_students = db.query(User).count()
    total_bot_interactions = db.query(InteractionLog).count()

    # Calculate Course Completion Rate
    total_sessions = db.query(QuizSession).count()
    completed_sessions = db.query(QuizSession).filter(QuizSession.is_completed == True).count()
    completion_rate = (completed_sessions / total_sessions) * 100 if total_sessions > 0 else 0

    # Calculate Learning Hours
    total_seconds = db.query(func.sum(InteractionLog.time_taken)).scalar() or 0
    learning_hours = total_seconds / 3600

    stats = [
        DashboardStat(
            title="Total Students",
            value=f"{total_students}",
            change="+12.5%", # Placeholder
            trend="up",      # Placeholder
            description="Active learners this month" # Placeholder
        ),
        DashboardStat(
            title="Course Completion",
            value=f"{completion_rate:.1f}%",
            change="+5.2%", # Placeholder
            trend="up",      # Placeholder
            description="Average completion rate" # Placeholder
        ),
        DashboardStat(
            title="Bot Interactions",
            value=f"{total_bot_interactions}",
            change="+23.1%", # Placeholder
            trend="up",      # Placeholder
            description="AI assistance requests" # Placeholder
        ),
        DashboardStat(
            title="Learning Hours",
            value=f"{learning_hours:.2f}",
            change="+8.7%", # Placeholder
            trend="up",      # Placeholder
            description="Total study time this week" # Placeholder
        ),
    ]
    return stats

@router.get("/recent-activity", response_model=List[RecentActivity])
async def get_recent_activity(db: Session = Depends(get_db)):
    # Fetch recent quiz sessions and interaction logs
    # For simplicity, we'll combine them and sort by timestamp
    recent_quiz_sessions = db.query(QuizSession).order_by(QuizSession.started_at.desc()).limit(5).all()
    recent_interaction_logs = db.query(InteractionLog).order_by(InteractionLog.timestamp.desc()).limit(5).all()

    activity_items = []

    for session in recent_quiz_sessions:
        user = db.query(User).filter(User.id == session.user_id).first()
        course = db.query(Course).filter(Course.id == session.course_id).first()
        if user and course:
            action = f"started {course.name}"
            if session.is_completed:
                action = f"completed {course.name}"
            
            # Ensure timestamp is timezone-aware (UTC)
            timestamp = None
            if session.is_completed and session.completed_at:
                timestamp = session.completed_at.astimezone(timezone.utc)
            elif session.started_at:
                timestamp = session.started_at.astimezone(timezone.utc)
            
            if timestamp:
                activity_items.append(RecentActivity(
                    id=f"quiz_session_{session.id}",
                    user=UserActivity(name=f"User {user.telegram_id}", avatar_initial=str(user.telegram_id)[0]),
                    action=action,
                    timestamp=timestamp
                ))

    for log in recent_interaction_logs:
        user = db.query(User).filter(User.id == log.user_id).first()
        question_course = db.query(Course).join(Course.questions).filter(Course.questions.any(id=log.question_id)).first()
        if user and question_course:
            action = f"answered a question in {question_course.name}"
            
            # Ensure timestamp is timezone-aware (UTC)
            timestamp = None
            if log.timestamp:
                timestamp = log.timestamp.astimezone(timezone.utc)

            if timestamp:
                activity_items.append(RecentActivity(
                    id=f"interaction_log_{log.id}",
                    user=UserActivity(name=f"User {user.telegram_id}", avatar_initial=str(user.telegram_id)[0]),
                    action=action,
                    timestamp=timestamp
                ))

    # Sort all activities by timestamp in descending order
    activity_items.sort(key=lambda x: x.timestamp, reverse=True)

    return activity_items[:10] # Return top 10 recent activities