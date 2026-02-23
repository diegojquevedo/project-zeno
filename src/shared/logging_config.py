"""
Re-exports logging from core. Prefer importing from src.core.logging.
"""

from src.core.logging import (
    bind_request_logging_context,
    configure_structlog,
    get_logger,
    setup_standard_logging,
)

__all__ = [
    "bind_request_logging_context",
    "configure_structlog",
    "get_logger",
    "setup_standard_logging",
]
