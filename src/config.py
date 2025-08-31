import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment Configuration
APP_ENV = os.getenv("APP_ENV", "development")

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# AWS S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

# Validate that essential variables are set
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

# JWT Authentication Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable not set. This is crucial for JWT security.")

# Admin & Feedback Configuration
ADMIN_USERNAMES_STR = os.getenv("ADMIN_USERNAMES", "")
ADMIN_USERNAMES = [username.strip() for username in ADMIN_USERNAMES_STR.split(",") if username.strip()]
TELEGRAM_ADMIN_GROUP_ID_STR = os.getenv("TELEGRAM_ADMIN_GROUP_ID")
TELEGRAM_ADMIN_GROUP_ID = int(TELEGRAM_ADMIN_GROUP_ID_STR) if TELEGRAM_ADMIN_GROUP_ID_STR else None

# Static Text Configuration
# Static Text Configuration
WELCOME_MESSAGE = """
Welcome to AskTheSageQuizzer! 🧠

I'm here to help you master your courses with personalized quizzes that adapt to your learning pace.

To get started, simply send /quiz.

Here are the available commands:
/quiz - Start a new adaptive quiz.
/performance - See your progress and quiz history.
/feedback - Have a suggestion or an issue? Let us know!
/help - Show this message again.

Happy studying!

---
*AskTheSageQuizzer is a product of HCX Technologies, a subsidiary of HCX Industries.*
*For inquiries, contact us at info@askthe.online.*
*For administrative matters (non-customer support), reach the admins at admin@askthe.online.*
"""
# Adaptive Quiz Configuration
ADAPTIVE_QUIZ_ENABLED = os.getenv("ADAPTIVE_QUIZ_ENABLED", "True").lower() == "true"

ADAPTIVE_QUIZ_CONFIG = {
    # Question selection weights
    'weakness_weight': 100,        # Priority for incorrect answers
    'new_question_weight': 50,     # Priority for new questions
    'srs_due_weight': 30,         # Priority for SRS review
    'srs_overdue_bonus': 20,      # Extra points for overdue questions
    'random_review_weight': 5,     # Lowest priority for random review
    
    # Target distribution percentages
    'target_weakness_pct': 0.60,   # 60% weakness questions
    'target_new_pct': 0.25,        # 25% new questions
    'target_srs_pct': 0.15,        # 15% SRS questions
    
    # SRS intervals (days) - works for all subjects
    'srs_intervals': [1, 3, 7, 14, 30, 60, 120, 240, 480],
    
    # Minimum attempts needed for reliable statistics
    'min_attempts_for_stats': 3,
}

# Course-specific overrides (optional)
COURSE_CONFIGS = {
    'french': {
        'target_weakness_pct': 0.50,  # Less weakness focus for language
        'target_new_pct': 0.35,       # More new vocabulary
        'srs_intervals': [1, 2, 5, 10, 20, 45, 90, 180, 360]  # Faster intervals
    },
    'mathematics': {
        'target_weakness_pct': 0.70,  # More weakness focus for math
        'target_new_pct': 0.20,
        'srs_intervals': [2, 5, 10, 21, 45, 90, 180, 365, 730]  # Slower intervals
    },
    'electronics': {
        'target_weakness_pct': 0.65,  # Standard technical subject
        'target_new_pct': 0.25,
        'srs_intervals': [1, 3, 7, 14, 30, 60, 120, 240, 480]  # Standard intervals
    }
}

# Time Limit Configuration
TIME_LIMIT_CONFIG = {
    'base_time': 45,  # seconds
    'tiers': {
        # difficulty_score: multiplier
        1.5: 1.0,
        3.0: 1.5,
        4.5: 2.0,
        6.75: 2.5,
    }
}

# "Guided Placement" Quiz Configuration for new users
DIFFICULTY_BANDS = {
    "easy": 1.5,
    "medium": 3.0,
    "hard": float('inf')
}
