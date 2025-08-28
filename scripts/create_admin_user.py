import os
import sys
import logging
from dotenv import load_dotenv

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

# Setup logging
from src.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from src.database import SessionLocal
from src.models.models import User
from src.api.auth_utils import get_password_hash

def create_admin_user():
    """
    Creates a default admin user if one doesn't already exist.
    """
    db = SessionLocal()

    try:
        # --- Check if admin user already exists ---
        admin_user = db.query(User).filter_by(username="hackeron").first()
        if admin_user:
            logger.info("Admin user 'hackeron' already exists.")
            return

        # --- Create Admin User ---
        hashed_password = get_password_hash("admin")
        new_admin = User(
            username="hackeron",
            full_name="Kevin  Nchorbuno",
            email="nchorkevin@gmail.com",
            hashed_password=hashed_password,
            is_admin=True
        )
        db.add(new_admin)
        db.commit()
        logger.info("Admin user 'Kevin' created successfully.")
        logger.info("Username: hackeron")
        logger.info("Password: hackeronhacker1")

    except Exception as e:
        db.rollback()
        logger.error(f"An error occurred while creating the admin user: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
