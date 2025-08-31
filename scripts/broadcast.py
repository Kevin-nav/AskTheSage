# scripts/broadcast.py
import asyncio
import argparse
import sys
import os
from telegram import Bot
import logging

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import TELEGRAM_BOT_TOKEN
from src.services.broadcast_service import get_all_user_ids, broadcast_to_users
from src.logging_config import setup_logging

# Setup logging for the script
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    parser = argparse.ArgumentParser(
        description="Send a broadcast message to all bot users.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--message", 
        type=str, 
        help="The message/caption content. Use '\n' for newlines."
    )
    parser.add_argument(
        "--file", 
        type=str, 
        help="Path to a file containing the message/caption content."
    )
    
    # Media group - photo or document, but not both
    media_group = parser.add_mutually_exclusive_group()
    media_group.add_argument(
        "--photo",
        type=str,
        help="Optional path to a photo to attach."
    )
    media_group.add_argument(
        "--document",
        type=str,
        help="Optional path to a document (e.g., .txt, .pdf) to attach."
    )
    
    args = parser.parse_args()

    # A message/caption is required if sending a photo or document
    if (args.photo or args.document) and not (args.message or args.file):
        parser.error("A --message or --file is required to provide a caption for the media.")

    # A message or file is required if no media is sent
    if not args.photo and not args.document and not (args.message or args.file):
        parser.error("You must provide a --message, --file, --photo, or --document.")

    # Check if media files exist
    if args.photo and not os.path.exists(args.photo):
        logger.error(f"Error: Photo file not found at '{args.photo}'")
        return
    if args.document and not os.path.exists(args.document):
        logger.error(f"Error: Document file not found at '{args.document}'")
        return

    message_text = ""
    if args.message:
        message_text = args.message.replace("\\n", "\n")
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                message_text = f.read()
        except FileNotFoundError:
            logger.error(f"Error: File not found at '{args.file}'")
            return
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return

    logger.info("Fetching user IDs from database...")
    try:
        user_ids = get_all_user_ids()
    except Exception as e:
        logger.error(f"Error fetching user IDs from the database: {e}")
        return
    
    if not user_ids:
        logger.info("No users found in the database to broadcast to.")
        return

    print("\n" + "-" * 30)
    print("         BROADCAST CONFIRMATION")
    print("-" * 30)
    print(f"The following will be sent to {len(user_ids)} user(s).")
    if args.photo:
        print(f"Photo Attachment: {args.photo}")
    if args.document:
        print(f"Document Attachment: {args.document}")
    if message_text.strip():
        print("\n--- MESSAGE/CAPTION CONTENT ---")
        print(message_text)
        print("-----------------------------" + "\n")

    try:
        confirm = input("ARE YOU SURE you want to send this broadcast? (y/N): ")
    except KeyboardInterrupt:
        print("\nBroadcast cancelled by user.")
        return

    if confirm.lower() != 'y':
        print("Broadcast cancelled.")
        return

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment.")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await broadcast_to_users(bot, user_ids, message_text, args.photo, args.document)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
