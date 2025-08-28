from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from src.api.dependencies import get_db
from src.api.schemas import ContactMessageCreate, ContactMessageResponse
from src.models.models import ContactMessage

router = APIRouter(
    prefix="/api/v1/contact",
    tags=["Contact"],
)

@router.post("/", response_model=ContactMessageResponse, status_code=status.HTTP_201_CREATED)
async def submit_contact_message(
    message: ContactMessageCreate,
    db: Session = Depends(get_db)
):
    """
    Submits a new contact message from the landing page.
    """
    db_message = ContactMessage(
        name=message.name,
        email=message.email,
        subject=message.subject,
        message=message.message,
        telegram_username=message.telegram_username,
        whatsapp_number=message.whatsapp_number,
        created_at=datetime.now(),
        is_read=False
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

@router.get("/success", status_code=status.HTTP_200_OK)
async def contact_success_message():
    """
    Returns a friendly success message after a contact form submission.
    """
    return {"message": "Thank you for reaching out! We've received your message and will get back to you as soon as possible. Your feedback helps us improve!"}
