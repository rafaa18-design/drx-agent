"""OpenTelemetry tracing configuration.

Provides distributed tracing with OpenTelemetry, exporting traces to:
- Generic OTLP endpoint (e.g., Jaeger, Tempo) when OTEL_ENABLED=true
- Langfuse OTEL endpoint when LANGFUSE_ENABLED=true (for LLM cost/token tracking)

When Langfuse OTEL is enabled, Agno agent LLM calls are automatically
instrumented via OpenInference AgnoInstrumentor.
"""

import base64
import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

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

        if has_langfuse:
            try:
                from openinference.instrumentation.agno import AgnoInstrumentor
                AgnoInstrumentor().instrument(tracer_provider=provider)
                logger.info('Agno instrumented with OpenInference -> Langfuse')
            except Exception as e:
                logger.warning('AgnoInstrumentor not available: %s', e)

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
