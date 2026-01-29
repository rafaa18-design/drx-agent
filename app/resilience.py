"""Resilience patterns for external service calls.

Provides retry with exponential backoff and circuit breaker patterns
for handling transient failures gracefully.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from tenacity import (AsyncRetrying, RetryError, retry_if_exception_type,
                      stop_after_attempt, wait_exponential)

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Retry with Exponential Backoff
# =============================================================================


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs,
) -> T:
    """Execute a function with retry and exponential backoff.

    Args:
        func: The async function to execute.
        *args: Positional arguments for the function.
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time between retries (seconds).
        max_wait: Maximum wait time between retries (seconds).
        retry_exceptions: Tuple of exception types to retry on.
        **kwargs: Keyword arguments for the function.

    Returns:
        The result of the function call.

    Raises:
        The last exception if all retries fail.
    """
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_exceptions),
            reraise=True,
        ):
            with attempt:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
    except RetryError:
        raise


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator to add retry with exponential backoff to a function.

    Args:
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time between retries (seconds).
        max_wait: Maximum wait time between retries (seconds).
        retry_exceptions: Tuple of exception types to retry on.

    Returns:
        Decorated function with retry logic.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_with_backoff(
                func,
                *args,
                max_attempts=max_attempts,
                min_wait=min_wait,
                max_wait=max_wait,
                retry_exceptions=retry_exceptions,
                **kwargs,
            )

        return wrapper

    return decorator


# =============================================================================
# Circuit Breaker
# =============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = 'closed'  # Normal operation
    OPEN = 'open'  # Failing, reject requests
    HALF_OPEN = 'half_open'  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    The circuit breaker pattern prevents cascading failures by stopping
    requests to a failing service temporarily.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service has recovered

    Usage:
        breaker = CircuitBreaker(name='model-api')

        async def call_model():
            async with breaker:
                return await model.generate(...)
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

    # Internal state
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    success_count: int = field(default=0)
    last_failure_time: float | None = field(default=None)
    half_open_calls: int = field(default=0)

    def __post_init__(self):
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """Check if request can proceed."""
        async with self._lock:
            await self._check_state()

            if self.state == CircuitState.OPEN:
                logger.warning(
                    f'Circuit breaker {self.name} is OPEN, rejecting request'
                )
                raise CircuitBreakerOpen(
                    f'Circuit breaker {self.name} is open'
                )

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpen(
                        f'Circuit breaker {self.name} half-open limit reached'
                    )
                self.half_open_calls += 1

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Record success or failure."""
        async with self._lock:
            if exc_type is None:
                await self._on_success()
            else:
                await self._on_failure()

        return False  # Don't suppress exceptions

    async def _check_state(self):
        """Check and potentially update circuit state."""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    logger.info(
                        f'Circuit breaker {self.name} transitioning to HALF_OPEN'
                    )
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0

    async def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                logger.info(
                    f'Circuit breaker {self.name} transitioning to CLOSED'
                )
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    async def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(
                f'Circuit breaker {self.name} transitioning to OPEN '
                f'(failure in half-open state)'
            )
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    f'Circuit breaker {self.name} transitioning to OPEN '
                    f'(threshold reached: {self.failure_count})'
                )
                self.state = CircuitState.OPEN

    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        logger.info(f'Circuit breaker {self.name} manually reset')

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'last_failure_time': self.last_failure_time,
            'recovery_timeout': self.recovery_timeout,
        }


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""

    pass


# =============================================================================
# Global Circuit Breakers
# =============================================================================

# Circuit breaker for LLM API calls
model_circuit_breaker = CircuitBreaker(
    name='model-api',
    failure_threshold=5,
    recovery_timeout=30.0,
)

# Circuit breaker for Redis calls
redis_circuit_breaker = CircuitBreaker(
    name='redis',
    failure_threshold=3,
    recovery_timeout=15.0,
)


def get_circuit_breaker_status() -> dict[str, dict[str, Any]]:
    """Get status of all circuit breakers."""
    return {
        'model_api': model_circuit_breaker.get_status(),
        'redis': redis_circuit_breaker.get_status(),
    }
