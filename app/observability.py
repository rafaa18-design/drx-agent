"""Observability: logging, tracing, and Langfuse client.

Consolidates:
- Structured logging (JSON/text) with request ID context
- OpenTelemetry tracing with OTLP and Langfuse exporters
- Langfuse SDK client for prompt management
"""

import base64
import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from langfuse import Langfuse
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tracing (OpenTelemetry)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def setup_tracing(app=None):
    has_otel = settings.OTEL_ENABLED and settings.OTEL_EXPORTER_OTLP_ENDPOINT
    has_langfuse = (
        settings.LANGFUSE_ENABLED
        and settings.LANGFUSE_PUBLIC_KEY
        and settings.LANGFUSE_SECRET_KEY
    )

    if not has_otel and not has_langfuse:
        logger.info('OpenTelemetry tracing disabled (no exporters configured)')
        return

    try:
        resource = Resource.create(
            {
                'service.name': settings.MODULE_ID,
                'service.version': settings.MODULE_VERSION,
                'deployment.environment': settings.OTEL_ENVIRONMENT,
            }
        )

        provider = TracerProvider(resource=resource)

        if has_otel:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as GrpcSpanExporter,
            )
            grpc_exporter = GrpcSpanExporter(
                endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                insecure=settings.OTEL_EXPORTER_OTLP_INSECURE,
            )
            provider.add_span_processor(BatchSpanProcessor(grpc_exporter))
            logger.info('OTEL gRPC exporter configured: %s', settings.OTEL_EXPORTER_OTLP_ENDPOINT)

        if has_langfuse:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter as HttpSpanExporter,
            )
            langfuse_auth = base64.b64encode(
                f'{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}'.encode()
            ).decode()
            langfuse_exporter = HttpSpanExporter(
                endpoint=f'{settings.LANGFUSE_BASE_URL}/api/public/otel/v1/traces',
                headers={'Authorization': f'Basic {langfuse_auth}'},
            )
            provider.add_span_processor(BatchSpanProcessor(langfuse_exporter))
            logger.info('Langfuse OTEL exporter configured: %s', settings.LANGFUSE_BASE_URL)

        # Set provider globally BEFORE instrumenting libraries
        trace.set_tracer_provider(provider)

        if app is not None and has_otel:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app, excluded_urls='/health,/metrics')
            logger.info('FastAPI instrumented with OpenTelemetry')

    except Exception as e:
        logger.error('Failed to configure OpenTelemetry: %s', e)


def shutdown_tracing():
    provider = trace.get_tracer_provider()
    if hasattr(provider, 'shutdown'):
        provider.shutdown()
        logger.info('OpenTelemetry tracing shut down')


# ---------------------------------------------------------------------------
# Langfuse Client
# ---------------------------------------------------------------------------

_langfuse: Langfuse | None = None


def get_langfuse() -> Langfuse | None:
    """Get the Langfuse client instance.

    Returns None if Langfuse is not configured or disabled.
    """
    global _langfuse

    if not settings.LANGFUSE_ENABLED:
        return None

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.warning('Langfuse credentials not configured')
        return None

    if _langfuse is None:
        try:
            _langfuse = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_BASE_URL,
            )
            if _langfuse.auth_check():
                logger.info('Langfuse client authenticated successfully')
            else:
                logger.error('Langfuse authentication failed')
                _langfuse = None
        except Exception as e:
            logger.error(f'Failed to initialize Langfuse: {e}')
            _langfuse = None

    return _langfuse


def setup_langfuse_env():
    """Set Langfuse environment variables for SDK auto-initialization.

    The Langfuse SDK v3 reads these env vars via get_client() singleton.
    Also sets LANGFUSE_HOST for any LiteLLM native integration.
    """
    if not settings.LANGFUSE_ENABLED:
        return

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return

    import os

    os.environ['LANGFUSE_SECRET_KEY'] = settings.LANGFUSE_SECRET_KEY
    os.environ['LANGFUSE_PUBLIC_KEY'] = settings.LANGFUSE_PUBLIC_KEY
    os.environ['LANGFUSE_BASE_URL'] = settings.LANGFUSE_BASE_URL
    os.environ['LANGFUSE_HOST'] = settings.LANGFUSE_BASE_URL

    logger.info('Langfuse env vars configured for SDK tracing')


def shutdown_langfuse():
    """Shutdown the Langfuse client gracefully."""
    global _langfuse
    if _langfuse:
        try:
            _langfuse.flush()
            _langfuse.shutdown()
        except Exception as e:
            logger.error(f'Error shutting down Langfuse: {e}')
        finally:
            _langfuse = None
