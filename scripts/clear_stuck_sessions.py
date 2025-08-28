import os
import sys
import logging
from datetime import datetime, timezone

# Add root directory to path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db
from src.models.models import QuizSession

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_all_stuck_sessions():
    """Finds all active (incomplete) quiz sessions and marks them as completed."""
    with get_db() as db:
        try:
            stuck_sessions = db.query(QuizSession).filter(QuizSession.is_completed == False).all()

            if not stuck_sessions:
                logger.info("No stuck sessions found. Database is clean.")
                return

            logger.warning(f"Found {len(stuck_sessions)} stuck sessions. Marking them as complete...")

            for session in stuck_sessions:
                session.is_completed = True
                session.completed_at = datetime.now(timezone.utc)
                if session.final_score is None:
                    session.final_score = 0 # Mark score as 0 for incomplete quizzes
            
            db.commit()
            logger.info(f"\033[92mSuccessfully cleared {len(stuck_sessions)} stuck sessions.\033[0m")

        except Exception as e:
            logger.error(f"An error occurred while clearing stuck sessions: {e}", exc_info=True)
            db.rollback()

if __name__ == "__main__":
    clear_all_stuck_sessions()
