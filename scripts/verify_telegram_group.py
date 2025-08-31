import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_GROUP_ID_STR = os.getenv("TELEGRAM_ADMIN_GROUP_ID")

async def verify_group():
    """
    Verifies the Telegram admin group ID by fetching its details and sending a message.
    """
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    if not TELEGRAM_ADMIN_GROUP_ID_STR:
        print("Error: TELEGRAM_ADMIN_GROUP_ID environment variable not set.")
        return

    try:
        group_id = int(TELEGRAM_ADMIN_GROUP_ID_STR)
    except ValueError:
        print(f"Error: Invalid TELEGRAM_ADMIN_GROUP_ID '{TELEGRAM_ADMIN_GROUP_ID_STR}'. Must be an integer.")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    print(f"Bot initialized. Verifying group with ID: {group_id}")

    # 1. Fetch chat details
    try:
        print("\n--- Fetching Chat Details ---")
        chat = await bot.get_chat(chat_id=group_id)
        print("Successfully fetched chat details:")
        print(f"  - Title: {chat.title}")
        print(f"  - Type: {chat.type}")
        print(f"  - ID: {chat.id}")
        if chat.username:
            print(f"  - Username: @{chat.username}")
    except TelegramError as e:
        print(f"\nError fetching chat details: {e}")
        print("This usually means:")
        print("  - The bot is NOT a member of the group/channel.")
        print("  - The Group ID is incorrect.")
        print("  - The group/channel does not exist.")
        return  # Stop here if we can't even get chat details

    # 2. Send a test message
    try:
        print("\n--- Sending Test Message ---")
        message = await bot.send_message(
            chat_id=group_id,
            text="Hello from the verification script! If you see this, the bot is correctly configured to send messages to this group."
        )
        print("Successfully sent a test message.")
        print(f"  - Message ID: {message.message_id}")
    except TelegramError as e:
        print(f"\nError sending message: {e}")
        print("This could mean:")
        print("  - The bot is a member but does not have permission to send messages (e.g., in a channel).")
        print("  - The bot was kicked or banned after joining.")

if __name__ == "__main__":
    print("Running Telegram Group Verification Script...")
    asyncio.run(verify_group())
