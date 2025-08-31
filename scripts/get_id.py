import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def get_updates():
    """
    Fetches the latest updates for the bot to identify chat IDs.
    """
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    print("Bot initialized. Fetching updates...")
    print("Please send a message in the group you want to identify.")
    print("Then check the output below.\n")

    try:
        # Get updates, ignoring previous ones
        updates = await bot.get_updates(offset=-1, timeout=10, allowed_updates=['message'])
        if updates:
            # Clear the update queue by confirming the last one
            await bot.get_updates(offset=updates[-1].update_id + 1)

        print("Waiting for a new message... (Timeout in 30 seconds)")
        updates = await bot.get_updates(timeout=30, allowed_updates=['message'])
        
        if not updates:
            print("\nNo new messages found for the bot in the last 30 seconds.")
            print("Please try again: run the script, then send a message in your group.")
            return

        print("\n--- Found Messages ---")
        unique_chats = {}
        for update in updates:
            if update.message and update.message.chat:
                chat = update.message.chat
                unique_chats[chat.id] = chat
        
        for chat_id, chat in unique_chats.items():
            print(f"Message received in chat:")
            print(f"  - Title: '{chat.title}'")
            print(f"  - Type: '{chat.type}'")
            print(f"  - ID: {chat.id}")
            print("-" * 20)

    except TelegramError as e:
        print(f"An API error occurred: {e}")
        print("This might indicate a problem with your TELEGRAM_BOT_TOKEN.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(get_updates())
