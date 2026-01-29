"""Structured logging configuration.

Provides JSON logging for production and text logging for development.
Includes request ID context for distributed tracing.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.config import settings

# Context variable for request ID (set by middleware)
request_id_var: ContextVar[str | None] = ContextVar('request_id', default=None)


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            'timestamp': datetime.now(UTC).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_data['request_id'] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, default=str)


class TextFormatter(logging.Formatter):
    """Text log formatter for development environments."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = request_id_var.get()
        rid_str = f'[{request_id[:8]}] ' if request_id else ''

        base_format = (
            f'%(asctime)s | %(levelname)-8s | {rid_str}%(name)s | %(message)s'
        )
        formatter = logging.Formatter(base_format, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


def setup_logging():
    """Configure logging based on settings.

    Call this function early in application startup.
    """
    # Determine log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Choose formatter based on settings
    if settings.LOG_FORMAT.lower() == 'json':
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        f'Logging configured: level={settings.LOG_LEVEL}, '
        f'format={settings.LOG_FORMAT}'
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds extra context to log messages."""

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        # Add request ID to extra
        request_id = request_id_var.get()
        if request_id and 'extra' not in kwargs:
            kwargs['extra'] = {}
        if request_id:
            kwargs['extra']['request_id'] = request_id
        return msg, kwargs


def get_context_logger(name: str) -> LoggerAdapter:
    """Get a logger adapter that includes request context.

    Args:
        name: Logger name (usually __name__).

    Returns:
        LoggerAdapter with context support.
    """
    return LoggerAdapter(logging.getLogger(name), {})
