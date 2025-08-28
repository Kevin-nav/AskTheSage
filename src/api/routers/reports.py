from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional

from src.api.dependencies import get_db
from src.api.schemas import (
    QuestionReportCreate, QuestionReportResponse, ReportStats, MostReportedQuestion,
    QuestionReportUpdate, ReportPage, QuestionReportDetails,
    ContactMessageResponse, ContactMessagePage # New import
)
from src.models.models import QuestionReport, User, Question, Course, ContactMessage # New import
from src.api.routers.auth import get_current_user, get_current_admin_user

router = APIRouter(
    prefix="/api/v1",
    tags=["Reports"],
)

@router.post("/reports", response_model=QuestionReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    report: QuestionReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Ensure the question exists
    question = db.query(Question).filter(Question.id == report.question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    new_report = QuestionReport(
        question_id=report.question_id,
        user_id=current_user.id,
        username=current_user.username or current_user.full_name, # Use username or full_name
        reason=report.reason,
        status="open"
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

@router.get("/admin/reports", response_model=ReportPage)
async def get_all_reports(
    db: Session = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
    status_filter: str = Query(None, description="Filter by report status (e.g., 'open', 'closed')"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100)
):
    query = db.query(
        QuestionReport.id,
        QuestionReport.question_id,
        QuestionReport.user_id,
        QuestionReport.username,
        QuestionReport.reason,
        QuestionReport.status,
        QuestionReport.reported_at,
        Question.question_text,
        Course.name.label("course_name")
    ).join(Question, QuestionReport.question_id == Question.id).join(Course, Question.course_id == Course.id)

    if status_filter:
        query = query.filter(QuestionReport.status == status_filter)

    query = query.order_by(QuestionReport.reported_at.desc())
    
    total = query.count()
    report_items = query.offset((page - 1) * size).limit(size).all()

    reports = [
        QuestionReportDetails(
            id=r.id,
            question_id=r.question_id,
            user_id=r.user_id,
            username=r.username,
            reason=r.reason,
            status=r.status,
            reported_at=r.reported_at,
            question_text=r.question_text,
            course_name=r.course_name
        ) for r in report_items
    ]

    return ReportPage(
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
        items=reports
    )

@router.get("/admin/reports/stats", response_model=ReportStats)
async def get_report_stats(
    db: Session = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user)
):
    total_reports = db.query(QuestionReport).count()
    open_reports = db.query(QuestionReport).filter(QuestionReport.status == "open").count()
    closed_reports = db.query(QuestionReport).filter(QuestionReport.status == "closed").count()

    most_reported_questions = db.query(
        Question.id,
        Question.question_text,
        Course.name.label("course_name"),
        func.count(QuestionReport.id).label("report_count")
    ).join(QuestionReport, Question.id == QuestionReport.question_id).join(Course, Question.course_id == Course.id).group_by(Question.id, Question.question_text, Course.name).order_by(func.count(QuestionReport.id).desc()).limit(5).all()

    return ReportStats(
        total_reports=total_reports,
        open_reports=open_reports,
        closed_reports=closed_reports,
        most_reported_questions=[
            MostReportedQuestion(
                question_id=q.id,
                question_text=q.question_text,
                course_name=q.course_name,
                report_count=q.report_count
            ) for q in most_reported_questions
        ]
    )

@router.get("/admin/reports/{report_id}", response_model=QuestionReportDetails)
async def get_report_by_id(
    report_id: int,
    db: Session = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user)
):
    report = db.query(
        QuestionReport.id,
        QuestionReport.question_id,
        QuestionReport.user_id,
        QuestionReport.username,
        QuestionReport.reason,
        QuestionReport.status,
        QuestionReport.reported_at,
        Question.question_text,
        Course.name.label("course_name")
    ).join(Question, QuestionReport.question_id == Question.id).join(Course, Question.course_id == Course.id).filter(QuestionReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return QuestionReportDetails(
        id=report.id,
        question_id=report.question_id,
        user_id=report.user_id,
        username=report.username,
        reason=report.reason,
        status=report.status,
        reported_at=report.reported_at,
        question_text=report.question_text,
        course_name=report.course_name
    )

@router.patch("/admin/reports/{report_id}", response_model=QuestionReportResponse)
async def update_report_status(
    report_id: int,
    report_update: QuestionReportUpdate,
    db: Session = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user)
):
    report = db.query(QuestionReport).filter(QuestionReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    allowed_statuses = {"open", "closed", "resolved"}
    if report_update.status not in allowed_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}")

    report.status = report_update.status
    db.commit()
    db.refresh(report)
    return report

# --- Contact Message Management (Admin Only) ---

@router.get("/admin/contact-messages", response_model=ContactMessagePage)
async def get_all_contact_messages(
    db: Session = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user),
    is_read_filter: Optional[bool] = Query(None, description="Filter by read status"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100)
):
    query = db.query(ContactMessage)

    if is_read_filter is not None:
        query = query.filter(ContactMessage.is_read == is_read_filter)

    query = query.order_by(ContactMessage.created_at.desc())

    total = query.count()
    messages = query.offset((page - 1) * size).limit(size).all()

    return ContactMessagePage(
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
        items=[ContactMessageResponse.from_orm(msg) for msg in messages]
    )

@router.get("/admin/contact-messages/{message_id}", response_model=ContactMessageResponse)
async def get_contact_message_by_id(
    message_id: int,
    db: Session = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user)
):
    message = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact message not found")
    return message

@router.patch("/admin/contact-messages/{message_id}/read", response_model=ContactMessageResponse)
async def mark_contact_message_as_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_admin_user: User = Depends(get_current_admin_user)
):
    message = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact message not found")
    
    message.is_read = True
    db.commit()
    db.refresh(message)
    return message