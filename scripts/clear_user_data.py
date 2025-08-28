import os
import sys

import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DATABASE_URL
from src.models.models import Base, InteractionLog, QuizSessionQuestion, QuizSession, UserAnswer

def clear_user_data():
    """
    Connects to the database and clears all user-specific progress data.
    """
    if not DATABASE_URL:
        print("DATABASE_URL not configured. Please check your .env file.")
        return

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Define the order of deletion to respect foreign key constraints
    tables_to_clear = [
        InteractionLog.__tablename__,
        QuizSessionQuestion.__tablename__,
        UserAnswer.__tablename__,
        QuizSession.__tablename__,
    ]

    try:
        print("Clearing user progress data in the correct order...")
        for table in tables_to_clear:
            print(f"  - Deleting all records from {table}...")
            # Using TRUNCATE ... RESTART IDENTITY CASCADE to handle dependencies
            session.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE;'))
        
        session.commit()
        print("\nAll user progress data has been successfully cleared.")

    except Exception as e:
        session.rollback()
        print(f"\nAn error occurred: {e}")
        print("Operation rolled back. No data was changed.")
    finally:
        session.close()
        print("Database session closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear user progress data from the database.")
    parser.add_argument('--force', action='store_true', help='Execute the deletion. Without this flag, the script will only show what would be deleted.')
    parser.add_argument('--yes', action='store_true', help='Bypass interactive confirmation.')
    args = parser.parse_args()

    if args.force:
        if args.yes:
            clear_user_data()
        else:
            print("This script will permanently delete all user quiz history and progress.")
            confirm = input("Are you sure you want to continue? (yes/no): ")
            if confirm.lower() == 'yes':
                clear_user_data()
            else:
                print("Operation cancelled.")
    else:
        print("This is a dry run. Run with --force to execute.")
