# Adaptive Learning Telegram Bot

## Project Overview

This project aims to create a highly effective and user-friendly Telegram bot that helps students master any subject through a personalized, adaptive learning system. The bot will use a hybrid spaced repetition algorithm and on-demand content rendering (including image and text generation) to deliver a dynamic and engaging learning experience. Our primary target users are high school and early college students studying various courses, preparing for examinations using past questions and AI-generated content.

## Core Features

*   **User Interaction & Navigation:** Intuitive navigation using Telegram's inline keyboards and a state-based conversation flow (`python-telegram-bot`'s `ConversationHandler`).
*   **Smart Question Selection Algorithm:** A hybrid algorithm that prioritizes questions based on user weakness, ensures broad coverage of topics, and incorporates spaced repetition principles.
*   **On-Demand Content Rendering:** Ability to render complex content (like mathematical equations) as images using libraries like Matplotlib, with a two-tier caching strategy (in-memory and Amazon S3).
*   **Quiz Interface:** Questions presented as Telegram polls for a clean, single-tap answering experience.
*   **Issue Reporting System:** Users can report issues with questions for continuous improvement of the question bank.

## Architecture & Technology Stack

*   **Programming Language:** Python 3.x
*   **Telegram Bot Framework:** `python-telegram-bot`
*   **Database:** PostgreSQL (local for development, AWS RDS for production)
*   **ORM (Object-Relational Mapper):** SQLAlchemy
*   **Database Migrations:** Alembic
*   **Environment Variables:** `python-dotenv`
*   **Cloud Infrastructure (Production Target):**
    *   Amazon EC2 (dual instances for high availability, single for development)
    *   Amazon RDS for PostgreSQL
    *   Amazon S3 (for content storage and image caching)
    *   Nginx (for load balancing and reverse proxy in production)

## Project Structure

Our project follows a clean, layered architecture for maintainability and scalability:

```
Johnson_Bot/
├── src/
│   ├── __init__.py
│   ├── models/         # Database definitions (models.py)
│   │   └── __init__.py
│   ├── services/       # Core business logic (e.g., navigation_service.py, quiz_service.py)
│   │   └── __init__.py
│   ├── handlers/       # Telegram-specific logic (e.g., conversation_handlers.py, general_handlers.py)
│   │   └── __init__.py
│   └── database.py     # Database connection setup
├── scripts/            # Utility scripts (e.g., seed_db.py)
│   └── __init__.py
├── alembic/            # Database migrations (managed by Alembic)
│   └── versions/       # Individual migration scripts
├── .env                # Environment variables (local development only - DO NOT COMMIT)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Setup & Local Development Guide

Follow these steps to set up the project on your local machine:

### 1. Prerequisites

*   Python 3.9+ installed.
*   PostgreSQL database server installed and running locally.

### 2. Database Setup

*   **Create Database and User:** Open your PostgreSQL client (e.g., `psql` or pgAdmin) and run the following SQL commands to create a database and a user for your bot:

    ```sql
    CREATE DATABASE adaptive_bot_local_db;
    CREATE USER bot_user WITH PASSWORD 'a_very_strong_password'; -- Replace with a strong password
    GRANT ALL PRIVILEGES ON DATABASE adaptive_bot_local_db TO bot_user;
    GRANT ALL ON SCHEMA public TO bot_user;
    ```

*   **Configure `.env` file:** Create a file named `.env` in the root of your project (`Johnson_Bot/`) and add your database connection string. **Replace `a_very_strong_password` with the actual password you set.**

    ```
    DATABASE_URL="postgresql://bot_user:a_very_strong_password@localhost:5432/adaptive_bot_local_db"
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN_HERE"
    ```

### 3. Project Setup

*   **Clone the Repository:** (Once the project is in a Git repository)
    ```bash
    git clone <repository_url>
    cd Johnson_Bot
    ```
*   **Create and Activate Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: .\venv\Scripts\activate
    ```
*   **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### 4. Database Migrations (Alembic)

*   **Apply Migrations:** This will create all the necessary tables in your database.
    ```bash
    alembic upgrade head
    ```

### 5. Seed Initial Data

*   **Populate Database:** Run the seeding script to add initial faculties, programs, levels, and sample questions.
    ```bash
    python scripts/seed_db.py
    ```

### 6. Run the Bot

*   **Start the Application:** Ensure your virtual environment is active and run:
    ```bash
    python -m src.main
    ```

## Progress So Far (What We've Done)

We've made significant progress in building the foundation and core features of the bot:

*   **Project Planning:** Defined high-level vision, core features, and architectural plan.
*   **Local Development Environment:** Set up local PostgreSQL, Python virtual environment, and dependency management.
*   **Professional Structure:** Implemented a clean, layered project structure (`src/models`, `src/services`, `src/handlers`, `scripts`).
*   **Database Management:** Integrated SQLAlchemy for ORM and Alembic for robust database migrations.
*   **Comprehensive Schema:** Designed and implemented a detailed database schema including:
    *   `Faculties`, `Programs`, `Levels`, `Courses` (with many-to-many relationships).
    *   `Users`, `Questions`, `UserAnswers` (for adaptive learning logic).
    *   `QuizSessions`, `QuizSessionQuestions` (for managing active quizzes).
*   **Data Seeding:** Developed a script to populate the database with initial navigation data and sample questions.
*   **User Navigation Flow:** Implemented the full multi-step navigation (`/quiz` -> Faculty -> Program -> Level -> Course) using Telegram inline keyboards.
*   **General Commands:** Implemented `/start` and `/help` commands with introductory messages.
*   **Core Quiz Engine (Initial):**
    *   Implemented `quiz_service` to start quiz sessions and select questions (basic smart algorithm).
    *   Integrated Telegram polls for question presentation and answer collection.
    *   Implemented basic answer processing and feedback.
*   **Error Resolution:** Successfully debugged and resolved various setup, database permission, and Python import/pathing errors.

## Next Steps

Our immediate focus will be on refining and expanding the core quiz engine and preparing for content rendering:

*   **Refine Smart Algorithm:** Implement the spaced repetition (SM-2) model for question scheduling.
*   **On-Demand Content Rendering:** Integrate Matplotlib for LaTeX rendering and implement S3 caching for images.
*   **More Question Types:** Expand beyond simple multiple-choice questions.
*   **User Feedback & Reporting:** Implement the issue reporting system.
*   **Gamification:** Add elements like points, badges, or leaderboards.
*   **Comprehensive Testing & Error Handling:** Implement robust testing procedures and improve error handling throughout the application.
*   **Deployment:** Prepare the application for deployment to AWS EC2.

## Question Management Script (`scripts/question_manager.py`)

This script provides a powerful and flexible way to manage quiz questions in your database, including automatic LaTeX rendering and uploading images to an S3 bucket.

### How to Use

**Arguments:**

*   `--course-name <COURSE_NAME>`: The exact name of the course (e.g., "Basic Electronics"). This argument is **required**.
*   `--json-file <PATH_TO_JSON>`: The absolute path to your JSON file containing question data. This argument is **required**.
*   `--operation <OPERATION>`: The operation to perform. Choose from:
    *   `add`: Adds new questions from the JSON file. It will skip any questions that are duplicates (based on content hash) of existing questions in the course.
    *   `update`: Updates existing questions in the course. It identifies questions by their content hash. If a question from the JSON file has a matching hash in the database, it will be updated. Questions not found will be skipped.
    *   `replace_all`: **CAUTION:** This operation will **delete all existing questions** for the specified course in the database and then load all questions from the provided JSON file.
*   `--dry-run`: (Optional) If present, the script will simulate the operations without making any actual changes to the database or S3. Useful for testing.
*   `--force-render`: (Optional) If present, LaTeX images will be re-rendered and re-uploaded to S3, even if a cached version already exists.

### JSON File Format

Your JSON file should be a list of question objects, each with the following structure:

```json
[
  {
    "question_text": "What is the capital of France? $\alpha + \beta$",
    "options": ["Berlin", "Madrid", "Paris", "Rome"],
    "correct_answer_index": 2,
    "explanation": "Paris is the capital and most populous city of France.",
    "has_latex": true,
    "difficulty_score": 0.7
  },
  {
    "question_text": "Which of the following is a primary color?",
    "options": ["Green", "Blue", "Yellow", "Orange"],
    "correct_answer_index": 1,
    "explanation": "Primary colors are Red, Yellow, and Blue.",
    "has_latex": false,
    "difficulty_score": 0.3
  }
]
```

*   `question_text`: The text of the question. Include LaTeX within `$` delimiters.
*   `options`: A list of strings for the multiple-choice options.
*   `correct_answer_index`: The 0-based index of the correct answer in the `options` list.
*   `explanation`: (Optional) The explanation for the answer. Can also contain LaTeX.
*   `has_latex`: (Boolean) Set to `true` if `question_text` or `explanation` contains LaTeX that needs rendering.
*   `difficulty_score`: (Optional) A float representing the difficulty.

### Examples

1.  **Add new questions to "Basic Electronics":**
    ```bash
    python scripts/question_manager.py --course-name "Basic Electronics" --json-file "C:\Users\MORO\Project\other_projects\Johnson_Bot\formatted_questions\basic_electronics_parts\basic_electronics_questions.json" --operation add
    ```

2.  **Replace all questions for "Basic French II":**
    ```bash
    python scripts/question_manager.py --course-name "Basic French II" --json-file "C:\Users\MORO\Project\other_projects\Johnson_Bot\formatted_questions\basic_french_2\basic_french_questions.json" --operation replace_all
    ```

3.  **Update existing questions in "Object Oriented Programming" (dry run):**
    ```bash
    python scripts/question_manager.py --course-name "Object Oriented Programming" --json-file "/path/to/your/oop_updates.json" --operation update --dry-run
    ```

4.  **Add new questions and force re-rendering of LaTeX:**
    ```bash
    python scripts/question_manager.py --course-name "New Science Course" --json-file "/path/to/your/science_questions.json" --operation add --force-render
    ```