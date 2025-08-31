import os
import sys
import logging
import argparse
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

def promote_user_to_admin(telegram_id, password):
    """
    Finds a user by their Telegram ID and promotes them to an admin,
    setting their password for web dashboard access.
    """
    db = SessionLocal()

    try:
        # --- Find user by Telegram ID ---
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            logger.error(f"User with Telegram ID '{telegram_id}' not found.")
            logger.info("The user must first interact with the bot to be registered in the database.")
            return

        if user.is_admin:
            logger.info(f"User '{user.username}' (Telegram ID: {telegram_id}) is already an admin.")
        else:
            user.is_admin = True
            logger.info(f"User '{user.username}' (Telegram ID: {telegram_id}) has been promoted to admin.")

        # --- Set/Update Password ---
        if password:
            user.hashed_password = get_password_hash(password)
            logger.info(f"Password for user '{user.username}' has been set.")
        
        db.commit()
        logger.info("Promotion and password setting complete.")

    except Exception as e:
        db.rollback()
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Promote a user to admin by their Telegram ID.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('telegram_id', type=int, help="The Telegram ID of the user to promote.")
    parser.add_argument(
        '--password',
        type=str,
        help="Optional: A new password for the user for web dashboard access.\nIf not provided, the password will not be changed."
    )
    args = parser.parse_args()
    
    promote_user_to_admin(args.telegram_id, args.password)