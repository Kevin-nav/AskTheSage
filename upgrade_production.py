import subprocess
import sys
import logging
from pathlib import Path
import time

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('upgrade_production.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
BROADCAST_SCRIPT = PROJECT_ROOT / "scripts" / "broadcast_release_notes.py"
BOT_SERVICE_NAME = "my-telegram-bot.service" # As specified in your systemd setup

# --- Helper Functions ---
def run_command(command: list[str], description: str, cwd: Path = PROJECT_ROOT, check: bool = True) -> bool:
    """Runs a command and logs its output, returning success status."""
    logger.info(f"--- {description} ---")
    try:
        # Prepend 'sudo' to systemctl commands as they require root privileges.
        # The script itself should be run by a user with sudo access.
        if "systemctl" in command[0]:
            command.insert(0, "sudo")
            
        logger.info(f"Executing command: {' '.join(command)}")
        process = subprocess.run(command, cwd=cwd, check=check, capture_output=True, text=True)
        
        if process.stdout:
            logger.info(f"Stdout: {process.stdout.strip()}")
        if process.stderr:
            logger.warning(f"Stderr: {process.stderr.strip()}")
            
        logger.info(f"Successfully completed: {description}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to {description}. Return code: {e.returncode}")
        logger.error(f"Command: {' '.join(e.cmd)}")
        logger.error(f"Stdout: {e.stdout.strip()}")
        logger.error(f"Stderr: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during '{description}': {e}")
        return False

def restart_bot_service() -> bool:
    """Restarts the Telegram bot using systemd."""
    logger.info("--- Restarting Telegram Bot Service via systemd ---")
    if not run_command(["systemctl", "restart", BOT_SERVICE_NAME], "Restarting bot service"):
        logger.error("Failed to restart the bot service. Please check the systemd service status manually using:")
        logger.error(f"  sudo systemctl status {BOT_SERVICE_NAME}")
        return False
    
    logger.info("Waiting a few seconds for the service to initialize...")
    time.sleep(5)
    
    # Check status after restart
    return run_command(["systemctl", "is-active", "--quiet", BOT_SERVICE_NAME], "Checking if bot service is active")

def notify_users_of_update() -> bool:
    """Runs the dedicated script to broadcast release notes."""
    logger.info("--- Notifying Users of Update ---")
    # Based on your systemd file, the python executable is in the venv
    python_executable = "/home/ubuntu/AskTheSageQ/venv/bin/python"
    
    if not Path(python_executable).exists():
        logger.error(f"Python executable not found at '{python_executable}'. Please update the path in this upgrade script.")
        # Fallback to the python that is running this script
        python_executable = sys.executable
        logger.warning(f"Falling back to using '{python_executable}'. This may not be the correct virtual environment.")

    return run_command([python_executable, str(BROADCAST_SCRIPT)], "Broadcasting release notes")

def main_upgrade_flow():
    """The main workflow for upgrading the Telegram bot."""
    logger.info("Starting Production Upgrade for Johnson_Bot (Telegram Bot Only)...")
    logger.warning("This script uses 'sudo' for systemd commands. Please run it with a user that has sudo privileges.")
    logger.warning("This script will NOT manage the FastAPI web server. You must restart it manually if needed.")

    steps = [
        (lambda: run_command(["git", "pull"], "Pull Latest Code from Git"), "Code Update"),
        (lambda: run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)], "Install/Update Python Dependencies"), "Dependency Installation"),
        (lambda: run_command(["alembic", "upgrade", "head"], "Apply Database Migrations"), "Database Migration"),
        (restart_bot_service, "Restart Telegram Bot Service"),
        (notify_users_of_update, "Notify Users of the Update")
    ]

    for step_func, step_name in steps:
        logger.info(f"\n===== Running Step: {step_name} =====")
        if not step_func():
            logger.error(f"Upgrade failed during step: {step_name}")
            logger.error("The application might be in a partially upgraded state. Manual intervention is required.")
            sys.exit(1)
        time.sleep(1)

    logger.info("\n===== All bot upgrade steps completed successfully! =====")
    logger.info("The Telegram bot has been restarted and users have been notified.")
    logger.info("REMINDER: Please restart your FastAPI server manually if it was affected by the code changes.")
    logger.info("Upgrade script finished.")

if __name__ == "__main__":
    main_upgrade_flow()
