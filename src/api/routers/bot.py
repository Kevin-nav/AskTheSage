from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.api.dependencies import get_db
from src.api.schemas import InteractionDetail, InteractionPage, BotStats
from src.models.models import InteractionLog, User, Question, Course

from src.api.routers.auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/bot",
    tags=["Admin Bot Interactions"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/stats", response_model=BotStats)
async def get_bot_stats(db: Session = Depends(get_db)):
    # Calculate average response time
    avg_time = db.query(func.avg(InteractionLog.time_taken)).scalar() or 0

    # Calculate accuracy rate
    total_interactions = db.query(InteractionLog).count()
    correct_interactions = db.query(InteractionLog).filter(InteractionLog.is_correct == True).count()
    accuracy_rate = (correct_interactions / total_interactions) * 100 if total_interactions > 0 else 0

    return BotStats(
        avg_response_time=avg_time,
        accuracy_rate=accuracy_rate
    )

@router.get("/interactions", response_model=InteractionPage)
async def get_bot_interactions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    sort_by: str = Query("timestamp", description="Field to sort by"),
    sort_dir: str = Query("desc", description="Sort direction (asc/desc)"),
):
    # Main query
    query = db.query(
        InteractionLog.id,
        User.full_name,
        User.username,
        Question.question_text,
        Course.name.label("course_name"),
        InteractionLog.is_correct,
        InteractionLog.time_taken,
        InteractionLog.timestamp
    ).join(User, InteractionLog.user_id == User.id).join(Question, InteractionLog.question_id == Question.id).join(Course, Question.course_id == Course.id)

    # Sorting
    if hasattr(InteractionLog, sort_by):
        sort_col = getattr(InteractionLog, sort_by)
        if sort_dir == "desc":
            sort_col = sort_col.desc()
        query = query.order_by(sort_col)

    # Pagination
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    interaction_details = [
        InteractionDetail(
            id=item.id,
            user_name=item.full_name or item.username or f"User {item.id}",
            question_text=item.question_text,
            course_name=item.course_name,
            is_correct=item.is_correct,
            time_taken=item.time_taken,
            timestamp=item.timestamp
        ) for item in items
    ]

    return InteractionPage(
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
        items=interaction_details
    )