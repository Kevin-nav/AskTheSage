from src.database import get_db
from src.models.models import User, QuizSession
from sqlalchemy import and_

TELEGRAM_ID = 5135164547

with get_db() as db:
    user = db.query(User).filter_by(telegram_id=TELEGRAM_ID).first()
    if user:
        updated_count = db.query(QuizSession).filter(
            and_(
                QuizSession.user_id == user.id,
                QuizSession.is_completed == False
            )
        ).update({"is_completed": True})
        db.commit()
        print(f"Marked {updated_count} incomplete sessions for user {user.id} as completed.")
    else:
        print(f"User with Telegram ID {TELEGRAM_ID} not found.")
