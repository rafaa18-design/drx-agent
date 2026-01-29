"""Redis-based rate limiting for distributed deployments.

Provides a sliding window rate limiter that works across multiple
application instances using Redis as a shared backend.
Falls back to in-memory rate limiting if Redis is unavailable.
"""

import logging
import time
from dataclasses import dataclass

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.metrics import record_rate_limit_hit

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_time: int
    retry_after: int | None = None


class RedisRateLimiter:
    """Sliding window rate limiter using Redis.

    Uses a sorted set to track request timestamps per client,
    enabling accurate rate limiting across distributed instances.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
    ):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self._memory_store: dict[str, list[float]] = {}

    async def _get_redis(self):
        """Get Redis client, returns None if unavailable."""
        try:
            from app.storage import get_redis

            return await get_redis()
        except Exception:
            return None

    def _rate_limit_key(self, client_id: str) -> str:
        """Generate Redis key for rate limiting."""
        return f'ratelimit:{client_id}'

    async def check_rate_limit(self, client_id: str) -> RateLimitResult:
        """Check if client has exceeded rate limit.

        Args:
            client_id: Unique client identifier.

        Returns:
            RateLimitResult with allowed status and metadata.
        """
        redis = await self._get_redis()

        if redis is None:
            return await self._check_memory_limit(client_id)

        try:
            return await self._check_redis_limit(redis, client_id)
        except Exception as e:
            logger.warning(f'Redis rate limit check failed: {e}')
            return await self._check_memory_limit(client_id)

    async def _check_redis_limit(
        self, redis, client_id: str
    ) -> RateLimitResult:
        """Check rate limit using Redis sorted set."""
        key = self._rate_limit_key(client_id)
        now = time.time()
        window_start = now - self.window_seconds

        # Use pipeline for atomic operations
        pipe = redis.pipeline()

        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Set expiry
        pipe.expire(key, self.window_seconds)

        results = await pipe.execute()
        current_count = results[1]

        remaining = max(0, self.requests_per_minute - current_count - 1)
        reset_time = int(now + self.window_seconds)

        if current_count >= self.requests_per_minute:
            # Remove the request we just added since it's over limit
            await redis.zrem(key, str(now))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=self.window_seconds,
            )

        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=reset_time,
        )

    async def _check_memory_limit(self, client_id: str) -> RateLimitResult:
        """Fallback in-memory rate limiting."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        if client_id in self._memory_store:
            self._memory_store[client_id] = [
                t for t in self._memory_store[client_id] if t > window_start
            ]
        else:
            self._memory_store[client_id] = []

        current_count = len(self._memory_store[client_id])
        remaining = max(0, self.requests_per_minute - current_count - 1)
        reset_time = int(now + self.window_seconds)

        if current_count >= self.requests_per_minute:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=self.window_seconds,
            )

        self._memory_store[client_id].append(now)
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=reset_time,
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting.

    Uses Redis for distributed rate limiting when available,
    falls back to in-memory limiting otherwise.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.limiter = RedisRateLimiter(
            requests_per_minute=requests_per_minute
        )

    def _get_client_id(self, request: Request) -> tuple[str, str]:
        """Get client identifier and type from request.

        Returns:
            Tuple of (client_id, client_type).
        """
        # Try to get user from JWT token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            try:
                token = auth_header.split(' ')[1]
                payload = jwt.decode(
                    token,
                    settings.JWT_SECRET,
                    algorithms=[settings.JWT_ALGORITHM],
                )
                return f"user:{payload.get('sub', 'unknown')}", 'user'
            except Exception:
                pass

        # Fall back to IP address
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.client.host if request.client else 'unknown'

        return f'ip:{ip}', 'ip'

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        excluded_paths = ['/', '/health', '/docs', '/openapi.json', '/metrics']
        if request.url.path in excluded_paths:
            return await call_next(request)

        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client_id, client_type = self._get_client_id(request)
        result = await self.limiter.check_rate_limit(client_id)

        if not result.allowed:
            logger.warning(f'Rate limit exceeded for {client_id}')
            record_rate_limit_hit(client_type)

            # Audit log rate limiting
            try:
                from app.audit import audit_rate_limited

                audit_rate_limited(
                    client_id=client_id,
                    client_type=client_type,
                    resource=request.url.path,
                )
            except Exception:
                pass  # Don't fail request if audit logging fails

            return JSONResponse(
                status_code=429,
                content={
                    'detail': 'Rate limit exceeded. Please try again later.',
                    'retry_after': result.retry_after,
                },
                headers={
                    'Retry-After': str(result.retry_after),
                    'X-RateLimit-Limit': str(self.limiter.requests_per_minute),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(result.reset_time),
                },
            )

        response = await call_next(request)

        # Add rate limit headers to response
        response.headers['X-RateLimit-Limit'] = str(
            self.limiter.requests_per_minute
        )
        response.headers['X-RateLimit-Remaining'] = str(result.remaining)
        response.headers['X-RateLimit-Reset'] = str(result.reset_time)

        return response
