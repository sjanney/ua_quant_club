"""Rotating file logger for operational events."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.config import CONFIG


def get_logger(name: str) -> logging.Logger:
    """Return a module logger writing to ``logs/events.log`` with rotation.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        Configured logger at INFO level with rotating file handler.
    """
    log_cfg = CONFIG.get("logging", {})
    log_dir = Path(str(log_cfg.get("log_dir", "logs")))
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "events.log"
    max_bytes = int(log_cfg.get("max_bytes", 5_000_000))
    backup_count = int(log_cfg.get("backup_count", 5))

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fmt = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger
