"""Prometheus metrics for monitoring and observability.

Exposes metrics about request counts, latencies, and errors.
Access via /metrics endpoint.
"""

import time
from functools import wraps
from typing import Callable

from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

# =============================================================================
# Metric Definitions
# =============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'endpoint'],
)

# Agent metrics
AGENT_RUN_COUNT = Counter(
    'agent_runs_total',
    'Total agent runs',
    ['status', 'model'],
)

AGENT_RUN_LATENCY = Histogram(
    'agent_run_duration_seconds',
    'Agent run latency in seconds',
    ['model'],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

AGENT_TOKENS_USED = Counter(
    'agent_tokens_total',
    'Total tokens used by agent',
    ['type', 'model'],  # type: input/output
)

# Error metrics
ERROR_COUNT = Counter(
    'errors_total',
    'Total errors',
    ['type', 'source'],
)

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['name'],
)

CIRCUIT_BREAKER_FAILURES = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['name'],
)

# Rate limiting metrics
RATE_LIMIT_HITS = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['client_type'],  # user/ip
)

# Redis metrics
REDIS_OPERATIONS = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation', 'status'],  # status: success/failure/fallback
)

# Authentication metrics
AUTH_ATTEMPTS = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['status'],  # success/failure
)


# =============================================================================
# Metrics Middleware
# =============================================================================


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip metrics endpoint to avoid recursion
        if request.url.path == '/metrics':
            return await call_next(request)

        method = request.method
        # Normalize path for metrics (avoid high cardinality)
        path = self._normalize_path(request.url.path)

        REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time
            REQUEST_COUNT.labels(
                method=method, endpoint=path, status_code=status_code
            ).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=path).observe(
                duration
            )
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=path).dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path to reduce cardinality.

        Replaces dynamic segments (UUIDs, IDs) with placeholders.
        """
        import re

        # Replace UUIDs
        path = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{id}',
            path,
            flags=re.IGNORECASE,
        )
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        return path


# =============================================================================
# Metrics Helpers
# =============================================================================


def record_agent_run(
    status: str,
    model: str,
    latency_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
):
    """Record metrics for an agent run.

    Args:
        status: Run status (success/error).
        model: Model used for the run.
        latency_seconds: Run latency in seconds.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
    """
    AGENT_RUN_COUNT.labels(status=status, model=model).inc()
    AGENT_RUN_LATENCY.labels(model=model).observe(latency_seconds)

    if input_tokens > 0:
        AGENT_TOKENS_USED.labels(type='input', model=model).inc(input_tokens)
    if output_tokens > 0:
        AGENT_TOKENS_USED.labels(type='output', model=model).inc(output_tokens)


def record_error(error_type: str, source: str):
    """Record an error metric.

    Args:
        error_type: Type of error (e.g., 'validation', 'timeout').
        source: Source of error (e.g., 'model', 'redis').
    """
    ERROR_COUNT.labels(type=error_type, source=source).inc()


def record_circuit_breaker_state(name: str, state: str):
    """Record circuit breaker state.

    Args:
        name: Circuit breaker name.
        state: State ('closed', 'open', 'half_open').
    """
    state_value = {'closed': 0, 'open': 1, 'half_open': 2}.get(state, 0)
    CIRCUIT_BREAKER_STATE.labels(name=name).set(state_value)


def record_rate_limit_hit(client_type: str):
    """Record a rate limit hit.

    Args:
        client_type: Type of client ('user' or 'ip').
    """
    RATE_LIMIT_HITS.labels(client_type=client_type).inc()


def record_redis_operation(operation: str, status: str):
    """Record a Redis operation.

    Args:
        operation: Operation type (get/set/delete).
        status: Operation status (success/failure/fallback).
    """
    REDIS_OPERATIONS.labels(operation=operation, status=status).inc()


def record_auth_attempt(status: str):
    """Record an authentication attempt.

    Args:
        status: Attempt status (success/failure).
    """
    AUTH_ATTEMPTS.labels(status=status).inc()


# =============================================================================
# Metrics Endpoint
# =============================================================================


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_active_requests() -> int:
    """Get the current count of active in-flight requests.

    Used for graceful shutdown to wait for requests to complete.

    Returns:
        Number of active requests across all endpoints.
    """
    total = 0
    # Sum across all label combinations
    for metric in REQUEST_IN_PROGRESS.collect():
        for sample in metric.samples:
            if sample.name == 'http_requests_in_progress':
                total += int(sample.value)
    return total


def get_metrics_content_type() -> str:
    """Get content type for metrics response."""
    return CONTENT_TYPE_LATEST
