import logging
import sys
from typing import Any

from uvicorn.logging import DefaultFormatter
from src.infrastructure.config import settings

def setup_logger() -> logging.Logger:
    """Configures and returns the central logger for the application."""
    root_logger = logging.getLogger()

    # Avoid adding multiple handlers if setup_logger is called multiple times
    if root_logger.handlers:
        return logging.getLogger("ivr_tester")

    # Set log level based on environment
    log_level = logging.DEBUG if settings.app_env == "development" else logging.INFO
    root_logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Create formatter
    formatter = DefaultFormatter(
        "%(levelprefix)s %(asctime)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    # Add handler to root logger so all loggers are visible
    root_logger.addHandler(console_handler)

    return logging.getLogger("ivr_tester")

def get_logger(name: str) -> logging.Logger:
    """Returns a child logger."""
    return logging.getLogger(f"ivr_tester.{name}")
