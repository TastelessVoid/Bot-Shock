"""
Centralized logging configuration for Bot Shock.
"""

import logging
import shutil
import sys
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path

from botshock.constants import (
    CURRENT_LOG_FILENAME,
    LOG_COMPONENT_WIDTH,
    LOG_DIR,
    LOG_LEVEL_WIDTH,
    LOG_TIME_FORMAT,
    LOGGER_NAMESPACE,
    MAX_OLD_LOGS,
)


class ReadableFormatter(logging.Formatter):
    """
    Custom log formatter with aligned columns for better readability.

    Formats logs as: [timestamp] [level] [component] message
    Multi-line messages are indented to align with the first line.
    """

    def __init__(
        self,
        time_fmt: str = LOG_TIME_FORMAT,
        level_width: int = LOG_LEVEL_WIDTH,
        comp_width: int = LOG_COMPONENT_WIDTH,
        use_tabs: bool = False,
    ):
        super().__init__()
        self.time_fmt = time_fmt
        self.level_width = level_width
        self.comp_width = comp_width
        self.use_tabs = use_tabs

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with aligned columns."""
        # Shorten logger name if it starts with app namespace
        log_name = record.name
        if log_name.startswith(f"{LOGGER_NAMESPACE}."):
            log_name = log_name.split(f"{LOGGER_NAMESPACE}.", 1)[1]

        timestamp = self.formatTime(record, self.time_fmt)
        level = record.levelname
        component = log_name
        message = record.getMessage() or ""

        if self.use_tabs:
            prefix = f"[{timestamp}]\t[{level}]\t[{component}]\t"
            indent = " " * len(prefix)
            lines = message.splitlines() or [""]
            formatted = prefix + lines[0]
            if len(lines) > 1:
                formatted += "\n" + "\n".join(indent + line for line in lines[1:])
        else:
            level_str = level.ljust(self.level_width)[: self.level_width]
            comp_str = (component[: self.comp_width]).ljust(self.comp_width)
            prefix = f"[{timestamp}] [{level_str}] [{comp_str}] "
            lines = message.splitlines() or [""]
            formatted = prefix + lines[0]
            if len(lines) > 1:
                formatted += "\n" + "\n".join(" " * len(prefix) + line for line in lines[1:])

        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        elif getattr(record, "exc_text", None):
            formatted += "\n" + record.exc_text

        return formatted


def _prune_by_age(log_dir: Path, retention_days: int, pattern: str = "bot_*.log") -> None:
    """Delete log files older than the specified retention period.

    Args:
        log_dir: The directory containing log files.
        retention_days: Number of days to keep; files older than this will be deleted.
        pattern: Glob pattern for rotated log files.
    """
    if retention_days <= 0:
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    for p in log_dir.glob(pattern):
        with suppress(Exception):
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < cutoff:
                p.unlink()


def rotate_logs(
    log_dir: Path = LOG_DIR,
    current_log_name: str = CURRENT_LOG_FILENAME,
    max_old: int = MAX_OLD_LOGS,
    retention_days: int | None = None,
) -> None:
    """
    Rotate the existing current log into a timestamped backup and prune old backups.

    Args:
        log_dir: Directory containing log files.
        current_log_name: Name of the current log file.
        max_old: Maximum number of old log files to keep.
        retention_days: If provided and > 0, also prune files older than this many days.
    """
    log_dir.mkdir(exist_ok=True)
    current_log = log_dir / current_log_name

    if current_log.exists() and current_log.stat().st_size > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"bot_{timestamp}.log"
        backup_log = log_dir / backup_name
        shutil.copy2(current_log, backup_log)

        # Remove older backups beyond max_old
        log_files = sorted(log_dir.glob("bot_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in log_files[max_old:]:
            with suppress(Exception):
                old.unlink()

    # Time-based pruning (optional)
    if retention_days and retention_days > 0:
        _prune_by_age(log_dir, retention_days)


def _has_console_handler(root_logger: logging.Logger) -> bool:
    """Return True if a stdout/stderr StreamHandler is already attached.

    Note: FileHandler subclasses StreamHandler, so we explicitly exclude FileHandler
    and only consider handlers whose stream is stdout or stderr.
    """
    for h in root_logger.handlers:
        if isinstance(h, logging.FileHandler):
            continue
        if isinstance(h, logging.StreamHandler):
            stream = getattr(h, "stream", None)
            if stream in {sys.stdout, sys.stderr}:
                return True
    return False


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path = LOG_DIR,
    current_log_name: str = CURRENT_LOG_FILENAME,
    max_old: int | None = None,
    retention_days: int | None = None,
) -> logging.Logger:
    """
    Configure application logging with file and console handlers.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files.
        current_log_name: Name of the current log file.
        max_old: Override maximum number of old log files to keep (defaults to MAX_OLD_LOGS).
        retention_days: If provided and > 0, prune log files older than this many days.

    Returns:
        Logger instance for the application.
    """
    # Rotate logs before setting up new handlers
    rotate_logs(log_dir, current_log_name, max_old or MAX_OLD_LOGS, retention_days)

    formatter = ReadableFormatter()
    current_log_path = log_dir / current_log_name

    # File handler
    file_handler = logging.FileHandler(current_log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid adding duplicate handlers
    if not any(
        isinstance(h, logging.FileHandler)
        and getattr(h, "baseFilename", "") == str(current_log_path)
        for h in root_logger.handlers
    ):
        root_logger.addHandler(file_handler)

    # Important: FileHandler is a StreamHandler; only consider real console streams here
    if not _has_console_handler(root_logger):
        root_logger.addHandler(console_handler)

    # Return a namespaced logger for app components
    return logging.getLogger(LOGGER_NAMESPACE)
