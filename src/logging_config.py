# src/logging_config.py
import os
import sys
from typing import Callable

from loguru import logger

# Create logs/ directory if it doesn't exist
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Log file path
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def setup_logging() -> Callable[[], None]:
    """
    Configure loguru sinks and return a shutdown hook that flushes/tears down
    the async queue created by enqueue=True.
    """
    # Remove default handler (console only)
    logger.remove()

    sinks = [
        logger.add(
            LOG_FILE,
            rotation="10 MB",  # Rotate logs when file hits 10 MB
            retention="10 days",  # Keep old logs for 10 days
            compression="zip",  # Compress old logs
            level="DEBUG",  # Log level
            enqueue=True,  # Async/thread-safe
        ),
        # Console sink; default to DEBUG so dev logs appear in terminal
        logger.add(
            sys.stdout,
            level=os.getenv("LOG_CONSOLE_LEVEL", "DEBUG"),
            enqueue=True,
        ),
    ]

    def shutdown() -> None:
        for sink_id in sinks:
            logger.remove(sink_id)
        logger.complete()

    return shutdown


# Initialize logging once at import and expose shutdown hook
shutdown_logging = setup_logging()
