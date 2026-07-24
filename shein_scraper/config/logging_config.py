"""
Centralized logging configuration for the application.
"""
import logging
import sys
from logging.config import dictConfig
from pathlib import Path

# Define the root directory of the project
# This assumes the script is in shein_scraper/config
ROOT_DIR = Path(__file__).resolve().parent.parent

def get_logging_config(log_level: str = "INFO") -> dict:
    """
    Generates the logging configuration dictionary.
    
    Args:
        log_level: The root logging level, e.g., "INFO", "DEBUG".
        
    Returns:
        A dictionary with the logging configuration.
    """
    logs_dir = ROOT_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {
                "format": "%(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "filename": logs_dir / "scraper.log",
                "maxBytes": 10 * 1024 * 1024,  # 10 MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "httpx": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            # Add other libraries here to control their verbosity
        },
        "root": {
            "level": log_level.upper(),
            "handlers": ["console", "file"],
        },
    }

def setup_logging(log_level: str = "INFO"):
    """
    Configures logging for the entire application using dictConfig.
    
    Args:
        log_level: The desired root logging level.
    """
    config = get_logging_config(log_level)
    dictConfig(config)
    logging.info("Logging configured successfully.")

