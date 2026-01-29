"""OpenTelemetry tracing configuration.

Provides distributed tracing with OpenTelemetry, exporting traces
to configured OTLP endpoint (e.g., Jaeger, Tempo, etc.).
"""

import logging
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
    OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (BatchSpanProcessor,
                                            SimpleSpanProcessor)
from opentelemetry.trace import Span, Status, StatusCode

from app.config import settings

logger = logging.getLogger(__name__)

# Global tracer
_tracer: trace.Tracer | None = None


def setup_tracing(app=None):
    """Configure OpenTelemetry tracing.

    Args:
        app: Optional FastAPI app to instrument.
    """
    global _tracer

    if not settings.OTEL_ENABLED:
        logger.info('OpenTelemetry tracing disabled')
        return

    try:
        # Create resource with service info
        resource = Resource.create(
            {
                'service.name': settings.MODULE_ID,
                'service.version': settings.MODULE_VERSION,
                'deployment.environment': settings.OTEL_ENVIRONMENT,
            }
        )

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Configure exporter
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            exporter = OTLPSpanExporter(
                endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                insecure=settings.OTEL_EXPORTER_OTLP_INSECURE,
            )
            # Use batch processor for production
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            logger.info(
                f'OpenTelemetry configured with OTLP endpoint: '
                f'{settings.OTEL_EXPORTER_OTLP_ENDPOINT}'
            )

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer
        _tracer = trace.get_tracer(
            settings.MODULE_ID,
            settings.MODULE_VERSION,
        )

        # Instrument FastAPI if app provided
        if app is not None:
            FastAPIInstrumentor.instrument_app(
                app,
                excluded_urls='/health,/metrics',
            )
            logger.info('FastAPI instrumented with OpenTelemetry')

    except Exception as e:
        logger.error(f'Failed to configure OpenTelemetry: {e}')


def get_tracer() -> trace.Tracer:
    """Get the configured tracer.

    Returns a no-op tracer if tracing is not configured.
    """
    global _tracer
    if _tracer is None:
        return trace.get_tracer(settings.MODULE_ID)
    return _tracer


@contextmanager
def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
    """Create a new span as a context manager.

    Args:
        name: Span name.
        attributes: Optional span attributes.
        kind: Span kind (internal, server, client, etc.).

    Yields:
        The created span.

    Example:
        with create_span('process_request', {'user_id': user_id}) as span:
            result = process(request)
            span.set_attribute('result_size', len(result))
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def add_span_attributes(attributes: dict[str, Any]):
    """Add attributes to the current span.

    Args:
        attributes: Dictionary of attributes to add.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_exception(
    exception: Exception, attributes: dict[str, Any] | None = None
):
    """Record an exception in the current span.

    Args:
        exception: The exception to record.
        attributes: Optional additional attributes.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception, attributes=attributes)
        span.set_status(Status(StatusCode.ERROR, str(exception)))


def get_current_trace_id() -> str | None:
    """Get the current trace ID as a hex string.

    Returns:
        Trace ID or None if no active span.
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, '032x')
    return None


def get_current_span_id() -> str | None:
    """Get the current span ID as a hex string.

    Returns:
        Span ID or None if no active span.
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, '016x')
    return None


def shutdown_tracing():
    """Shutdown tracing and flush pending spans."""
    provider = trace.get_tracer_provider()
    if hasattr(provider, 'shutdown'):
        provider.shutdown()
        logger.info('OpenTelemetry tracing shut down')
