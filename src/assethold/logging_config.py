# ABOUTME: Configures loguru-based structured logging for assethold.
# ABOUTME: Provides console (INFO) and rotating file (DEBUG) handlers.
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

# Default log directory relative to the repo root
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_FILE = _LOG_DIR / "assethold.log"

# Rotation / retention settings for the file handler
_MAX_SIZE = "10 MB"
_BACKUP_COUNT = 5


def setup_logging() -> None:
    """Configure loguru handlers for console and rotating file output.

    Safe to call multiple times -- existing handlers are removed first.
    """
    logger.remove()  # clear default stderr handler

    # Console handler -- colorized, INFO level
    logger.add(
        sys.stderr,
        level="INFO",
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # Rotating file handler -- DEBUG level, structured
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(_LOG_FILE),
        level="DEBUG",
        rotation=_MAX_SIZE,
        retention=_BACKUP_COUNT,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
        enqueue=True,  # thread-safe writes
    )


# Re-export the configured logger for convenience
__all__ = ["logger", "setup_logging"]
