"""
Invoice Generator Logging Configuration
Provides structured logging using loguru.
"""

import sys
from pathlib import Path
from loguru import logger

from backend.config import settings


def setup_logging():
    """Configure application logging."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True,
    )

    # File handler
    logger.add(
        str(log_dir / "invoice_generator_{time:YYYY-MM-DD}.log"),
        rotation="10 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
    )

    logger.info(f"Invoice Generator {settings.APP_VERSION} logging initialized")


# Initialize on import
setup_logging()
