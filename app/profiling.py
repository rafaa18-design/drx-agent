"""Async profiling utilities for identifying performance bottlenecks.

Provides decorators and context managers for profiling async operations.
Results can be logged or exported to observability backends.
"""

import asyncio
import functools
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """Result of a profiling operation."""

    name: str
    duration_ms: float
    start_time: float
    end_time: float
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'name': self.name,
            'duration_ms': round(self.duration_ms, 3),
            'start_time': self.start_time,
            'end_time': self.end_time,
            'success': self.success,
            'error': self.error,
            **self.metadata,
        }


class AsyncProfiler:
    """Async operation profiler with aggregated statistics.

    Tracks timing statistics for named operations over time.
    Useful for identifying slow operations and performance trends.
    """

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self._samples: dict[str, list[ProfileResult]] = {}
        self._lock = asyncio.Lock()

    async def record(self, result: ProfileResult) -> None:
        """Record a profiling result."""
        async with self._lock:
            if result.name not in self._samples:
                self._samples[result.name] = []

            samples = self._samples[result.name]
            samples.append(result)

            # Trim to max samples
            if len(samples) > self.max_samples:
                self._samples[result.name] = samples[-self.max_samples :]

    def get_stats(self, name: str) -> dict[str, Any] | None:
        """Get statistics for a named operation.

        Returns:
            Dictionary with count, mean, min, max, p50, p95, p99 durations.
        """
        samples = self._samples.get(name)
        if not samples:
            return None

        durations = [s.duration_ms for s in samples]
        durations_sorted = sorted(durations)
        count = len(durations)

        return {
            'name': name,
            'count': count,
            'success_rate': sum(1 for s in samples if s.success) / count,
            'mean_ms': sum(durations) / count,
            'min_ms': min(durations),
            'max_ms': max(durations),
            'p50_ms': durations_sorted[int(count * 0.5)],
            'p95_ms': durations_sorted[int(count * 0.95)]
            if count >= 20
            else None,
            'p99_ms': durations_sorted[int(count * 0.99)]
            if count >= 100
            else None,
        }

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all tracked operations."""
        return {name: self.get_stats(name) for name in self._samples}

    def clear(self, name: str | None = None) -> None:
        """Clear samples for a specific operation or all operations."""
        if name:
            self._samples.pop(name, None)
        else:
            self._samples.clear()


# Global profiler instance
_profiler = AsyncProfiler()


def get_profiler() -> AsyncProfiler:
    """Get the global profiler instance."""
    return _profiler


@asynccontextmanager
async def profile_async(
    name: str,
    log_slow_threshold_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Context manager for profiling async operations.

    Args:
        name: Name of the operation being profiled.
        log_slow_threshold_ms: Log warning if duration exceeds this.
        metadata: Additional metadata to include in the result.

    Example:
        async with profile_async('database_query', log_slow_threshold_ms=100):
            result = await db.query(...)
    """
    start_time = time.perf_counter()
    error = None
    success = True

    try:
        yield
    except Exception as e:
        error = str(e)
        success = False
        raise
    finally:
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        result = ProfileResult(
            name=name,
            duration_ms=duration_ms,
            start_time=start_time,
            end_time=end_time,
            success=success,
            error=error,
            metadata=metadata or {},
        )

        # Record to profiler
        await _profiler.record(result)

        # Log slow operations
        if log_slow_threshold_ms and duration_ms > log_slow_threshold_ms:
            logger.warning(
                f'Slow operation detected: {name} took {duration_ms:.2f}ms '
                f'(threshold: {log_slow_threshold_ms}ms)',
                extra={'profile': result.to_dict()},
            )


def profile_async_function(
    name: str | None = None,
    log_slow_threshold_ms: float | None = None,
):
    """Decorator for profiling async functions.

    Args:
        name: Override name (default: function name).
        log_slow_threshold_ms: Log warning if duration exceeds this.

    Example:
        @profile_async_function(log_slow_threshold_ms=100)
        async def slow_operation():
            await asyncio.sleep(0.2)
    """

    def decorator(func: Callable) -> Callable:
        operation_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with profile_async(
                operation_name, log_slow_threshold_ms=log_slow_threshold_ms
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


async def profile_concurrent(
    operations: dict[str, Callable],
    log_slow_threshold_ms: float | None = None,
) -> dict[str, tuple[Any, ProfileResult]]:
    """Profile multiple concurrent async operations.

    Args:
        operations: Dictionary mapping names to async callables.
        log_slow_threshold_ms: Log warning if any operation exceeds this.

    Returns:
        Dictionary mapping names to (result, profile) tuples.

    Example:
        results = await profile_concurrent({
            'fetch_user': fetch_user(user_id),
            'fetch_orders': fetch_orders(user_id),
        })
    """
    results = {}

    async def profile_one(name: str, coro):
        start = time.perf_counter()
        error = None
        success = True
        result = None

        try:
            result = await coro
        except Exception as e:
            error = str(e)
            success = False
            raise
        finally:
            end = time.perf_counter()
            duration_ms = (end - start) * 1000

            profile = ProfileResult(
                name=name,
                duration_ms=duration_ms,
                start_time=start,
                end_time=end,
                success=success,
                error=error,
            )

            await _profiler.record(profile)

            if log_slow_threshold_ms and duration_ms > log_slow_threshold_ms:
                logger.warning(
                    f'Slow concurrent operation: {name} took {duration_ms:.2f}ms'
                )

            results[name] = (result, profile)

    await asyncio.gather(
        *(profile_one(name, coro) for name, coro in operations.items()),
        return_exceptions=True,
    )

    return results


# Middleware for profiling all requests
class ProfilingMiddleware:
    """ASGI middleware for profiling HTTP requests.

    Adds profiling data to all requests. Enable via settings.
    """

    def __init__(
        self, app, enabled: bool = True, log_slow_threshold_ms: float = 1000
    ):
        self.app = app
        self.enabled = enabled
        self.log_slow_threshold_ms = log_slow_threshold_ms

    async def __call__(self, scope, receive, send):
        if not self.enabled or scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        path = scope.get('path', 'unknown')
        method = scope.get('method', 'UNKNOWN')
        name = f'http.{method}.{path}'

        start = time.perf_counter()
        error = None
        success = True

        try:
            await self.app(scope, receive, send)
        except Exception as e:
            error = str(e)
            success = False
            raise
        finally:
            end = time.perf_counter()
            duration_ms = (end - start) * 1000

            result = ProfileResult(
                name=name,
                duration_ms=duration_ms,
                start_time=start,
                end_time=end,
                success=success,
                error=error,
                metadata={'method': method, 'path': path},
            )

            await _profiler.record(result)

            if duration_ms > self.log_slow_threshold_ms:
                logger.warning(
                    f'Slow request: {method} {path} took {duration_ms:.2f}ms',
                    extra={'profile': result.to_dict()},
                )
