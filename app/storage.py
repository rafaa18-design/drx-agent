"""Storage backends for session state and persistence.

Redis is used for session state, caching, and message history.

This module includes graceful fallback when Redis is unavailable,
allowing the application to continue operating in degraded mode.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Redis Client
# =============================================================================

_redis_client: aioredis.Redis | None = None
_redis_available: bool = True  # Track Redis availability


async def get_redis() -> aioredis.Redis | None:
    """Get Redis client with connection pooling.

    Returns None if Redis is unavailable, enabling graceful degradation.
    The connection pool is configured via settings:
    - REDIS_POOL_MIN_SIZE: Minimum connections in pool
    - REDIS_POOL_MAX_SIZE: Maximum connections in pool
    - REDIS_CONNECT_TIMEOUT: Connection timeout
    - REDIS_SOCKET_TIMEOUT: Socket operation timeout
    """
    global _redis_client, _redis_available

    if not _redis_available:
        return None

    if _redis_client is None:
        try:
            # Create connection pool with explicit configuration
            pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                encoding='utf-8',
                decode_responses=True,
                max_connections=settings.REDIS_POOL_MAX_SIZE,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            )
            _redis_client = aioredis.Redis(connection_pool=pool)
            await _redis_client.ping()
            logger.info(
                f'Redis connected with pool (max={settings.REDIS_POOL_MAX_SIZE})'
            )
        except Exception as e:
            logger.warning(f'Redis connection failed: {e}')
            _redis_available = False
            _redis_client = None
            return None

    return _redis_client


async def close_redis():
    """Close Redis connection."""
    global _redis_client, _redis_available
    if _redis_client:
        try:
            await _redis_client.aclose()
        except Exception as e:
            logger.warning(f'Error closing Redis connection: {e}')
        finally:
            _redis_client = None
    logger.info('Redis connection closed')


def is_redis_available() -> bool:
    """Check if Redis is available."""
    return _redis_available


async def get_redis_pool_stats() -> dict[str, int] | None:
    """Get Redis connection pool statistics.

    Returns:
        Dictionary with pool stats or None if Redis unavailable.
    """
    client = await get_redis()
    if client is None:
        return None

    try:
        pool = client.connection_pool
        return {
            'max_connections': pool.max_connections,
            'current_connections': len(pool._in_use_connections),
            'available_connections': pool.max_connections
            - len(pool._in_use_connections),
        }
    except Exception:
        return None


# =============================================================================
# Session State Operations
# =============================================================================


def _session_key(conversation_id: str) -> str:
    """Generate key for session state."""
    return f'{settings.AGENT_NAME}:session:{conversation_id}:state'


def _history_key(conversation_id: str) -> str:
    """Generate key for message history."""
    return f'{settings.AGENT_NAME}:session:{conversation_id}:history'


# In-memory fallback for when Redis is unavailable
_memory_store: dict[str, Any] = {}


async def get_session_state(conversation_id: str) -> dict[str, Any]:
    """Get session state from Redis (with in-memory fallback)."""
    client = await get_redis()

    if client is None:
        # Fallback to in-memory storage
        return _memory_store.get(_session_key(conversation_id), {})

    try:
        data = await client.get(_session_key(conversation_id))
        if data:
            return json.loads(data)
        return {}
    except Exception as e:
        logger.warning(f'Failed to get session state from Redis: {e}')
        return _memory_store.get(_session_key(conversation_id), {})


async def set_session_state(
    conversation_id: str,
    state: dict[str, Any],
    ttl: int | None = None,
):
    """Set session state in Redis (with in-memory fallback)."""
    key = _session_key(conversation_id)
    client = await get_redis()

    # Always store in memory as backup
    _memory_store[key] = state

    if client is None:
        logger.debug('Redis unavailable, using in-memory storage for session')
        return

    try:
        await client.set(
            key,
            json.dumps(state),
            ex=ttl or settings.REDIS_SESSION_TTL,
        )
    except Exception as e:
        logger.warning(f'Failed to set session state in Redis: {e}')


async def update_session_state(conversation_id: str, updates: dict[str, Any]):
    """Update session state (merge with existing)."""
    current = await get_session_state(conversation_id)
    current.update(updates)
    await set_session_state(conversation_id, current)


async def delete_session_state(conversation_id: str):
    """Delete session state from Redis and memory."""
    key = _session_key(conversation_id)

    # Remove from memory
    _memory_store.pop(key, None)

    client = await get_redis()
    if client is None:
        return

    try:
        await client.delete(key)
    except Exception as e:
        logger.warning(f'Failed to delete session state from Redis: {e}')


# =============================================================================
# Message History Operations
# =============================================================================

# In-memory history fallback
_history_store: dict[str, list[dict[str, Any]]] = {}


async def add_message_to_history(
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
):
    """Add message to history in Redis (with in-memory fallback)."""
    message = {
        'role': role,
        'content': content,
        'metadata': metadata or {},
    }

    key = _history_key(conversation_id)
    if settings.MEMORY_CONSOLIDATION_ENABLED:
        max_messages = settings.MEMORY_WINDOW * 2
    else:
        max_messages = settings.NUM_HISTORY_RUNS * 2

    # Always store in memory
    if key not in _history_store:
        _history_store[key] = []
    _history_store[key].append(message)
    # Trim to max size
    if len(_history_store[key]) > max_messages:
        _history_store[key] = _history_store[key][-max_messages:]

    client = await get_redis()
    if client is None:
        logger.debug('Redis unavailable, using in-memory storage for history')
        return

    try:
        await client.rpush(key, json.dumps(message))
        await client.ltrim(key, -max_messages, -1)
        await client.expire(key, settings.REDIS_SESSION_TTL)
    except Exception as e:
        logger.warning(f'Failed to add message to Redis history: {e}')


async def get_message_history(
    conversation_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Get message history from Redis (with in-memory fallback)."""
    if settings.MEMORY_CONSOLIDATION_ENABLED:
        limit = limit or settings.MEMORY_WINDOW * 2
    else:
        limit = limit or settings.NUM_HISTORY_RUNS * 2
    key = _history_key(conversation_id)

    client = await get_redis()

    if client is None:
        # Fallback to in-memory
        history = _history_store.get(key, [])
        return history[-limit:]

    try:
        messages = await client.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]
    except Exception as e:
        logger.warning(f'Failed to get history from Redis: {e}')
        history = _history_store.get(key, [])
        return history[-limit:]


async def clear_message_history(conversation_id: str):
    """Clear message history from Redis and memory."""
    key = _history_key(conversation_id)

    # Clear from memory
    _history_store.pop(key, None)

    client = await get_redis()
    if client is None:
        return

    try:
        await client.delete(key)
    except Exception as e:
        logger.warning(f'Failed to clear history from Redis: {e}')


# =============================================================================
# Cache Operations
# =============================================================================

# In-memory cache fallback
_cache_store: dict[str, Any] = {}


async def cache_get(key: str) -> Any | None:
    """Get value from cache in Redis (with in-memory fallback)."""
    cache_key = f'{settings.AGENT_NAME}:cache:{key}'

    client = await get_redis()

    if client is None:
        return _cache_store.get(cache_key)

    try:
        data = await client.get(cache_key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f'Failed to get from Redis cache: {e}')
        return _cache_store.get(cache_key)


async def cache_set(key: str, value: Any, ttl: int | None = None):
    """Set value in cache in Redis (with in-memory fallback)."""
    cache_key = f'{settings.AGENT_NAME}:cache:{key}'

    # Always store in memory
    _cache_store[cache_key] = value

    client = await get_redis()
    if client is None:
        logger.debug('Redis unavailable, using in-memory cache')
        return

    try:
        await client.set(
            cache_key,
            json.dumps(value),
            ex=ttl or settings.REDIS_CACHE_TTL,
        )
    except Exception as e:
        logger.warning(f'Failed to set Redis cache: {e}')


async def cache_delete(key: str):
    """Delete value from cache in Redis and memory."""
    cache_key = f'{settings.AGENT_NAME}:cache:{key}'

    # Remove from memory
    _cache_store.pop(cache_key, None)

    client = await get_redis()
    if client is None:
        return

    try:
        await client.delete(cache_key)
    except Exception as e:
        logger.warning(f'Failed to delete from Redis cache: {e}')


