import os
import sys
import logging
import argparse
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup logging
from src.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from src.database import SessionLocal
from src.models.models import User
from src.config import TELEGRAM_BOT_TOKEN
from src.api.auth_utils import get_password_hash

async def update_user_details(db_session, bot):
    """Fetches and updates user details for users with missing information."""
    users_to_update = db_session.query(User).filter(User.full_name == None).all()
    if not users_to_update:
        logger.info("No users need updating.")
        return

    logger.info(f"Found {len(users_to_update)} users with missing details. Fetching from Telegram...")
    for user in users_to_update:
        try:
            chat = await bot.get_chat(user.telegram_id)
            user.username = chat.username
            user.full_name = chat.full_name
            logger.info(f"  Updated details for User ID: {user.id} (Telegram ID: {user.telegram_id})")
        except TelegramError as e:
            logger.error(f"  Could not fetch details for User ID: {user.id} (Telegram ID: {user.telegram_id}). Error: {e}")
    db_session.commit()

def set_admin_status(db_session, user_ids, is_admin, password=None):
    """Sets the admin status and password for a list of user IDs."""
    if not user_ids:
        return

    action = "Promoting" if is_admin else "Demoting"
    logger.info(f"--- {action} Users ---")
    
    users_to_modify = db_session.query(User).filter(User.id.in_(user_ids)).all()
    
    if not users_to_modify:
        logger.warning("No users found for the given IDs.")
        return

    for user in users_to_modify:
        user.is_admin = is_admin
        log_message = f"  - User ID: {user.id} ({user.username}), New Admin Status: {user.is_admin}"
        
        if is_admin and password:
            user.hashed_password = get_password_hash(password)
            log_message += ", Password has been set."
        
        logger.info(log_message)
        
    db_session.commit()
    logger.info("-------------------------")


def list_users(db_session):
    """Lists all users in the database."""
    users = db_session.query(User).order_by(User.id).all()
    if not users:
        logger.info("No users found in the database.")
        return

    logger.info("--- Users in Database ---")
    for user in users:
        logger.info(
            f"  ID: {user.id}, "
            f"Telegram ID: {user.telegram_id}, "
            f"Username: {user.username}, "
            f"Full Name: {user.full_name}, "
            f"Is Admin: {user.is_admin}"
        )
    logger.info("-------------------------")

async def main():
    """Main function to manage admin users."""
    parser = argparse.ArgumentParser(description="Manage admin users.")
    parser.add_argument('--promote', nargs='+', type=int, help="List of user IDs to promote to admin.")
    parser.add_argument('--demote', nargs='+', type=int, help="List of user IDs to demote from admin.")
    parser.add_argument('--password', type=str, help="Set a password for the user(s) being promoted. Required with --promote.")
    parser.add_argument('--update', action='store_true', help="Update user details from Telegram.")
    parser.add_argument('--list', action='store_true', help="List all users.")
    args = parser.parse_args()

    db = SessionLocal()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    try:
        if args.update:
            await update_user_details(db, bot)
        
        if args.promote:
            if not args.password:
                logger.error("The --password argument is required when promoting users.")
            else:
                set_admin_status(db, args.promote, True, args.password)

        if args.demote:
            set_admin_status(db, args.demote, False)

        if args.list or not any(vars(args).values()):
            list_users(db)

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
