import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler

def setup_logging():
    """
    Configures logging for the application, using environment variables for configuration.
    Sets up a timed rotating file handler to create a new log file each day.
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = os.getenv("LOG_DIR", "logs") # Use a directory for logs
    log_file = os.path.join(log_dir, "bot.log")
    
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Get the root logger
    logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Timed Rotating File handler
    try:
        # Rotate log file at midnight, keep 30 days of backups
        file_handler = TimedRotatingFileHandler(
            log_file, 
            when="midnight", 
            interval=1, 
            backupCount=30, 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (IOError, OSError) as e:
        # If file handler fails, we log the error to the console and continue.
        logging.basicConfig() # Basic config for the error message to show up
        logging.error(f"Failed to create log file handler for {log_file}: {e}", exc_info=True)
