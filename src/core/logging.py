"""
Structured logging setup. Uses core.config for all env-based settings.
"""

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler

import structlog
from structlog.types import Processor

from src.core.config import settings


class ColorlessFormatter(logging.Formatter):
    """Custom formatter that strips ANSI color codes from log messages."""

    ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return self.ANSI_ESCAPE.sub("", formatted)


def get_log_level() -> int:
    """Get log level from settings."""
    level_name = settings.log_level.upper()
    return getattr(logging, level_name, logging.INFO)


def get_log_format() -> str:
    """Get log format from settings."""
    return settings.log_format.lower()


def should_log_to_file() -> bool:
    """Check if logging to file is enabled."""
    return settings.log_to_file


def get_log_file_path() -> str:
    """Get log file path from settings."""
    return settings.log_file_path


def configure_structlog() -> None:
    """Configure structlog with appropriate processors and output format."""
    shared_processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    log_format = get_log_format()

    if log_format == "json":
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                pad_event=28,
            )
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def setup_standard_logging() -> None:
    """Set up standard library logging handlers."""
    root_logger = logging.getLogger()

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    log_level = get_log_level()
    log_format = get_log_format()

    if log_format == "json":
        console_formatter = logging.Formatter("%(message)s")
        file_formatter = logging.Formatter("%(message)s")
    else:
        console_formatter = logging.Formatter("%(message)s")
        file_formatter = ColorlessFormatter("%(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(console_formatter)
    stream_handler.setLevel(log_level)
    root_logger.addHandler(stream_handler)

    if should_log_to_file():
        log_file_path = get_log_file_path()
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=10**6, backupCount=5
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(logging.DEBUG)


def _initialize_logging() -> None:
    """Run setup on module import."""
    setup_standard_logging()
    configure_structlog()


_initialize_logging()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger with the specified name."""
    return structlog.get_logger(name)


def bind_request_logging_context(**kwargs) -> None:
    """Bind request context for structured logging."""
    structlog.contextvars.bind_contextvars(**kwargs)
