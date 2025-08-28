import os
import subprocess
import sys
import shutil
from dotenv import load_dotenv
import logging
from pathlib import Path
import time

load_dotenv()

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deploy_to_ec2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
ALEMBIC_CONFIG = PROJECT_ROOT / "alembic.ini"
SEED_DB_SCRIPT = PROJECT_ROOT / "scripts" / "seed_db.py"
LOAD_FROM_CSV_SCRIPT = PROJECT_ROOT / "scripts" / "load_from_csv.py"
FASTAPI_MAIN_APP = "src.api.main:app"
TELEGRAM_BOT_MAIN_SCRIPT = PROJECT_ROOT / "src" / "main.py"

# --- Helper Functions ---
def run_command(command: list[str], description: str, cwd: Path = PROJECT_ROOT, check: bool = True) -> bool:
    logger.info(f"\n--- {description} ---")
    try:
        process = subprocess.run(command, cwd=cwd, check=check, capture_output=True, text=True)
        logger.info(process.stdout)
        if process.stderr:
            logger.warning(f"Stderr output: {process.stderr}")
        logger.info(f"Successfully completed: {description}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to {description}. Error: {e}")
        logger.error(f"Command: {' '.join(command)}")
        logger.error(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error(f"Command not found. Please ensure '{' '.join(command).split()[0]}' is installed and in your PATH.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during {description}: {e}")
        return False

def check_prerequisites() -> bool:
    logger.info("Checking prerequisites...")
    if sys.version_info < (3, 9):
        logger.error("Python 3.9 or higher is required.")
        return False
    if not shutil.which("pip"):
        logger.error("pip is not installed. Please install pip.")
        return False
    
    logger.info("Python and pip are available.")
    logger.info("\n--- External Tool Requirements ---")
    logger.info("Please ensure the following are installed on your EC2 instance:")
    logger.info("  - PostgreSQL database server (and accessible from this instance)")
    logger.info("  - TeX Live (for pdflatex) and ImageMagick (for convert/magick) for LaTeX rendering")
    logger.info("  - poppler-utils (for pdftocairo, required by pdf2image library)")
    logger.info("Without these, LaTeX rendering and image generation will fail.")
    return True

def install_python_dependencies() -> bool:
    return run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)], "Install Python dependencies")

def configure_environment_variables() -> bool:
    logger.info("\n--- Environment Variable Configuration ---")
    logger.info("Please ensure the following environment variables are set. You can create a '.env' file in the project root:")
    logger.info("  - DATABASE_URL=\"postgresql://user:password@host:port/dbname\"")
    logger.info("  - TELEGRAM_BOT_TOKEN=\"YOUR_BOT_TOKEN\"")
    logger.info("  - AWS_ACCESS_KEY_ID=\"YOUR_AWS_ACCESS_KEY\"")
    logger.info("  - AWS_SECRET_ACCESS_KEY=\"YOUR_AWS_SECRET_KEY\"")
    logger.info("  - S3_BUCKET_NAME=\"your-s3-bucket-name\"")
    logger.info("  - AWS_REGION=\"your-aws-region\" (e.g., eu-north-1)")
    logger.info("  - SECRET_KEY=\"a_long_random_string_for_fastapi_sessions\"")
    logger.info("  - LOG_DIR=\"logs\" (optional, default is 'logs')")
    logger.info("\nChecking for critical environment variables...")

    required_vars = ["DATABASE_URL", "TELEGRAM_BOT_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET_NAME", "AWS_REGION", "SECRET_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"The following critical environment variables are NOT set: {', '.join(missing_vars)}")
        logger.error("Please set them before proceeding. You can use a .env file and install 'python-dotenv'.")
        return False
    logger.info("All critical environment variables are set.")
    return True

def setup_database() -> bool:
    logger.info("\n--- Database Setup ---")
    if not run_command(["alembic", "upgrade", "head"], "Apply Alembic database migrations", cwd=PROJECT_ROOT):
        return False
    if not run_command([sys.executable, str(SEED_DB_SCRIPT)], "Seed initial database data (faculties, programs, levels)", cwd=PROJECT_ROOT):
        return False
    return True

def load_questions() -> bool:
    logger.info("\n--- Load Question Data ---")
    logger.info("Starting interactive CSV question loader. Follow the prompts to select CSVs and courses.")
    # The load_from_csv.py script is interactive, so we just run it.
    # It handles its own logging and user interaction.
    try:
        subprocess.run([sys.executable, str(LOAD_FROM_CSV_SCRIPT)], cwd=PROJECT_ROOT, check=True)
        logger.info("Successfully loaded questions from CSVs.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Interactive question loading failed. Error: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during question loading: {e}")
        return False

def provide_deployment_instructions():
    logger.info("\n--- Deployment Instructions ---")
    logger.info("The project setup is complete. Here's how to run your applications:")

    logger.info("\n1. Run FastAPI Backend (API for Dashboard and Bot Webhooks):")
    logger.info(f"   To run in development mode: uvicorn {FASTAPI_MAIN_APP} --host 0.0.0.0 --port 8000")
    logger.info("   For production, consider using Gunicorn with Nginx:")
    logger.info("     - Install Gunicorn: pip install gunicorn")
    logger.info(f"     - Run with Gunicorn (e.g., 4 workers): gunicorn -w 4 -k uvicorn.workers.UvicornWorker {FASTAPI_MAIN_APP} --bind 0.0.0.0:8000")
    logger.info("     - Configure Nginx as a reverse proxy to forward requests to Gunicorn.")
    logger.info("       (Refer to Nginx documentation for specific setup on your EC2 instance)")

    logger.info("\n2. Run Telegram Bot (if not using webhooks via FastAPI):")
    logger.info("   If your Telegram bot is configured to use long polling (not webhooks via FastAPI),")
    logger.info("   you can run the bot's main script directly:")
    logger.info(f"   {sys.executable} {TELEGRAM_BOT_MAIN_SCRIPT}")
    logger.info("   Note: If using FastAPI for webhooks, the bot logic is triggered via API calls, and this separate script might not be needed.")
    logger.info("   Consult your bot's configuration (e.g., `src/main.py` or `src/config.py`) to confirm its mode of operation.")

    logger.info("\n--- Important Security Note ---")
    logger.info("Ensure your .env file is NOT publicly accessible and environment variables are securely managed on your EC2 instance.")
    logger.info("Configure AWS IAM roles and policies for your EC2 instance to grant necessary S3 and RDS access, rather than using direct access keys if possible.")

def main_deployment_flow():
    logger.info("Starting EC2 Deployment Setup for Johnson_Bot Project...")

    steps = [
        (check_prerequisites, "Prerequisites Check"),
        (install_python_dependencies, "Python Dependencies Installation"),
        (configure_environment_variables, "Environment Variable Configuration"),
        (setup_database, "Database Setup (Migrations & Seeding)"),
        (load_questions, "Load Question Data from CSVs"),
    ]

    for step_func, step_name in steps:
        logger.info(f"\n===== Running Step: {step_name} =====")
        if not step_func():
            logger.error(f"Deployment failed during step: {step_name}")
            sys.exit(1)
        time.sleep(1) # Small delay for readability

    logger.info("\n===== All core setup steps completed successfully! =====")
    provide_deployment_instructions()
    logger.info("Deployment script finished.")

if __name__ == "__main__":
    try:
        # Ensure shutil is imported for check_prerequisites
        import shutil
        main_deployment_flow()
    except Exception as e:
        logger.critical(f"An unhandled critical error occurred during deployment: {e}")
        sys.exit(1)
