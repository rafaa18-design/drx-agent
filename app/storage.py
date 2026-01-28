"""Storage backends for session state and persistence.

Redis: Session state, cache, temporary data
PostgreSQL: Persistent storage, chat history, agent data
"""

import json
import logging
from typing import Any

import redis.asyncio as redis
from agno.db.postgres import PostgresDb

from app.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Redis Client (Session State & Cache)
# =============================================================================

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding='utf-8',
            decode_responses=True,
        )
        # Test connection
        try:
            await _redis_client.ping()
            logger.info('Redis connected successfully')
        except Exception as e:
            logger.error(f'Redis connection failed: {e}')
            raise

    return _redis_client


async def close_redis():
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info('Redis connection closed')


# =============================================================================
# Session State Operations (Redis)
# =============================================================================


def _session_key(conversation_id: str) -> str:
    """Generate Redis key for session state."""
    return f'session:{conversation_id}:state'


def _history_key(conversation_id: str) -> str:
    """Generate Redis key for message history."""
    return f'session:{conversation_id}:history'


async def get_session_state(conversation_id: str) -> dict[str, Any]:
    """Get session state from Redis."""
    client = await get_redis()
    data = await client.get(_session_key(conversation_id))
    if data:
        return json.loads(data)
    return {}


async def set_session_state(
    conversation_id: str,
    state: dict[str, Any],
    ttl: int | None = None,
):
    """Set session state in Redis."""
    client = await get_redis()
    await client.set(
        _session_key(conversation_id),
        json.dumps(state),
        ex=ttl or settings.REDIS_SESSION_TTL,
    )


async def update_session_state(conversation_id: str, updates: dict[str, Any]):
    """Update session state (merge with existing)."""
    current = await get_session_state(conversation_id)
    current.update(updates)
    await set_session_state(conversation_id, current)


async def delete_session_state(conversation_id: str):
    """Delete session state."""
    client = await get_redis()
    await client.delete(_session_key(conversation_id))


# =============================================================================
# Message History Operations (Redis for recent, PostgreSQL for persistent)
# =============================================================================


async def add_message_to_history(
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
):
    """Add message to Redis history (recent messages)."""
    client = await get_redis()
    message = json.dumps(
        {
            'role': role,
            'content': content,
            'metadata': metadata or {},
        }
    )
    await client.rpush(_history_key(conversation_id), message)
    # Keep only recent messages in Redis
    await client.ltrim(
        _history_key(conversation_id), -settings.NUM_HISTORY_RUNS * 2, -1
    )
    await client.expire(
        _history_key(conversation_id), settings.REDIS_SESSION_TTL
    )


async def get_message_history(
    conversation_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Get message history from Redis."""
    client = await get_redis()
    limit = limit or settings.NUM_HISTORY_RUNS * 2
    messages = await client.lrange(_history_key(conversation_id), -limit, -1)
    return [json.loads(m) for m in messages]


async def clear_message_history(conversation_id: str):
    """Clear message history."""
    client = await get_redis()
    await client.delete(_history_key(conversation_id))


# =============================================================================
# Cache Operations (Redis)
# =============================================================================


async def cache_get(key: str) -> Any | None:
    """Get value from cache."""
    client = await get_redis()
    data = await client.get(f'cache:{key}')
    if data:
        return json.loads(data)
    return None


async def cache_set(key: str, value: Any, ttl: int | None = None):
    """Set value in cache."""
    client = await get_redis()
    await client.set(
        f'cache:{key}',
        json.dumps(value),
        ex=ttl or settings.REDIS_CACHE_TTL,
    )


async def cache_delete(key: str):
    """Delete value from cache."""
    client = await get_redis()
    await client.delete(f'cache:{key}')


# =============================================================================
# PostgreSQL Database (Persistent Storage via Agno)
# =============================================================================

_postgres_db: PostgresDb | None = None


def get_postgres_db() -> PostgresDb:
    """Get PostgreSQL database instance for Agno."""
    global _postgres_db

    if _postgres_db is None:
        _postgres_db = PostgresDb(db_url=settings.POSTGRES_URL)
        logger.info('PostgreSQL database configured')

    return _postgres_db
