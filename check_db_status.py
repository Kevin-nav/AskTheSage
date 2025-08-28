from src.database import get_db
from src.models.models import User, QuizSession

TELEGRAM_ID = 5135164547

with get_db() as db:
    user = db.query(User).filter_by(telegram_id=TELEGRAM_ID).first()
    if user:
        print(f"Found user: {user.id} (Telegram ID: {user.telegram_id})")
        sessions = db.query(QuizSession).filter_by(user_id=user.id).order_by(QuizSession.started_at.desc()).all()
        if sessions:
            print("Quiz Sessions for this user:")
            for session in sessions:
                print(f"  Session ID: {session.id}, Completed: {session.is_completed}, "
                      f"Started At: {session.started_at}, Completed At: {session.completed_at}, "
                      f"Total Questions: {session.total_questions}, Final Score: {session.final_score}")
        else:
            print("No quiz sessions found for this user.")
    else:
        print(f"User with Telegram ID {TELEGRAM_ID} not found.")
