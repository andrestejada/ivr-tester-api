import logging
import sys
from typing import Any

from src.infrastructure.config import settings

def setup_logger() -> logging.Logger:
    """Configures and returns the central logger for the application."""
    logger = logging.getLogger("ivr_tester")
    
    # Avoid adding multiple handlers if setup_logger is called multiple times
    if logger.handlers:
        return logger

    # Set log level based on environment
    log_level = logging.DEBUG if settings.app_env == "development" else logging.INFO
    logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger

def get_logger(name: str) -> logging.Logger:
    """Returns a child logger."""
    return logging.getLogger(f"ivr_tester.{name}")
