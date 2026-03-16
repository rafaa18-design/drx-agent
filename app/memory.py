"""LLM-driven memory consolidation system.

Adapted from nanobot memory.py. Provides long-term memory via
periodic consolidation of conversation history into structured facts.

Resilience strategy:
- Retry with exponential backoff on transient LLM/Redis failures
- Auto-escalation of max_tokens on truncation (finish_reason=length)
- Circuit breaker to avoid hammering a failing LLM API
- Cooldown with exponential backoff between failed consolidation attempts
- Counter only resets on success — failed attempts are always retried

Redis keys per conversation:
- memory:{cid}:facts       → long-term facts (markdown string)
- memory:{cid}:log         → searchable log entries (Redis list)
- memory:{cid}:unconsolidated → counter of unconsolidated messages
- memory:{cid}:consolidation_failures → consecutive failure count
- memory:{cid}:consolidation_cooldown → timestamp until next attempt allowed
"""

import asyncio
import json
import logging
import time
from typing import Any

import litellm

from app.config import settings
from app.metrics import record_consolidation
from app.resilience import CircuitBreaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)

# Lock per session to prevent concurrent consolidations
_consolidation_locks: dict[str, asyncio.Lock] = {}

# Track active consolidation tasks for graceful shutdown
_active_tasks: set[asyncio.Task] = set()

# Circuit breaker for consolidation LLM calls
_consolidation_breaker = CircuitBreaker(
    name='memory-consolidation',
    failure_threshold=3,
    recovery_timeout=60.0,
    half_open_max_calls=1,
)

# Max consecutive failures before applying long cooldown
_MAX_CONSECUTIVE_FAILURES = 5
_BASE_COOLDOWN_SECONDS = 30  # doubles each failure: 30s, 60s, 120s, 240s, 300s(cap)
_MAX_COOLDOWN_SECONDS = 300  # 5 minutes cap


# =============================================================================
# Custom exception for retryable consolidation failures
# =============================================================================


class ConsolidationRetryable(Exception):
    """Raised when consolidation fails but can be retried."""

    pass


# =============================================================================
# Save Memory Tool Definition (used by consolidation LLM)
# =============================================================================

_SAVE_MEMORY_TOOL = {
    'type': 'function',
    'function': {
        'name': 'save_memory',
        'description': (
            'Save a history entry and updated memory facts. '
            'Call this to persist the consolidated information.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'history_entry': {
                    'type': 'string',
                    'description': (
                        'A 2-5 sentence summary of the recent conversation, '
                        'prefixed with [YYYY-MM-DD HH:MM]. Include key actions, '
                        'decisions, and outcomes.'
                    ),
                },
                'memory_update': {
                    'type': 'string',
                    'description': (
                        'Updated markdown containing ALL known facts about '
                        'the user/patient. Merge new information with existing '
                        'facts. Remove outdated information. Keep it concise '
                        'and well-organized with headers.'
                    ),
                },
            },
            'required': ['history_entry', 'memory_update'],
        },
    },
}

_CONSOLIDATION_SYSTEM_PROMPT = """\
You are a memory management assistant. Your job is to consolidate conversation \
history into structured long-term memory.

You will receive:
1. EXISTING MEMORY: Current known facts (may be empty for new conversations)
2. RECENT MESSAGES: New conversation messages to consolidate

Your task:
- Summarize the recent messages into a history_entry (2-5 sentences with timestamp)
- Update the memory_update with ALL known facts, merging new info with existing
- Remove outdated or contradicted information
- Keep facts organized by category (e.g., ## Dados Pessoais, ## Preferências, ## Histórico)
- Write in the same language as the conversation (Portuguese)
- Be concise but complete

IMPORTANT: Always call the save_memory tool with your results."""


# =============================================================================
# Redis Key Helpers
# =============================================================================


def _facts_key(cid: str) -> str:
    return f'memory:{cid}:facts'


def _log_key(cid: str) -> str:
    return f'memory:{cid}:log'


def _unconsolidated_key(cid: str) -> str:
    return f'memory:{cid}:unconsolidated'


def _last_consolidated_key(cid: str) -> str:
    return f'memory:{cid}:last_consolidated'


def _failures_key(cid: str) -> str:
    return f'memory:{cid}:consolidation_failures'


def _cooldown_key(cid: str) -> str:
    return f'memory:{cid}:consolidation_cooldown'


# =============================================================================
# Public API
# =============================================================================


async def clear_memory(cid: str) -> None:
    """Clear all memory-related Redis keys for a conversation.

    Removes facts, log, unconsolidated counter, consolidation failures,
    cooldown, and last_consolidated timestamp.
    """
    from app.storage import get_redis

    client = await get_redis()
    if client is None:
        return

    keys = [
        _facts_key(cid),
        _log_key(cid),
        _unconsolidated_key(cid),
        _last_consolidated_key(cid),
        _failures_key(cid),
        _cooldown_key(cid),
    ]

    try:
        await client.delete(*keys)
        logger.info(f'Memory cleared for {cid}')
    except Exception as e:
        logger.warning(f'Failed to clear memory for {cid}: {e}')


async def get_memory_context(cid: str) -> str:
    """Get formatted memory context for prompt injection.

    Args:
        cid: Conversation/session ID.

    Returns:
        Formatted string with long-term facts, or empty string.
    """
    from app.storage import get_redis

    client = await get_redis()
    if client is None:
        return ''

    try:
        facts = await client.get(_facts_key(cid))
        return facts or ''
    except Exception as e:
        logger.warning(f'Failed to get memory context for {cid}: {e}')
        return ''


async def increment_unconsolidated(cid: str) -> int:
    """Increment the unconsolidated message counter.

    Returns:
        The new counter value.
    """
    from app.storage import get_redis

    client = await get_redis()
    if client is None:
        return 0

    try:
        val = await client.incr(_unconsolidated_key(cid))
        await client.expire(
            _unconsolidated_key(cid), settings.REDIS_SESSION_TTL
        )
        return val
    except Exception as e:
        logger.warning(f'Failed to increment unconsolidated for {cid}: {e}')
        return 0


async def should_consolidate(cid: str) -> bool:
    """Check if consolidation should be triggered.

    Returns True when unconsolidated count >= MEMORY_WINDOW and no
    cooldown is active from previous failures.
    """
    from app.storage import get_redis

    client = await get_redis()
    if client is None:
        return False

    try:
        val = await client.get(_unconsolidated_key(cid))
        count = int(val) if val else 0
        if count < settings.MEMORY_WINDOW:
            return False

        # Check cooldown from previous failures
        cooldown_until = await client.get(_cooldown_key(cid))
        if cooldown_until:
            remaining = float(cooldown_until) - time.time()
            if remaining > 0:
                logger.debug(
                    f'Consolidation for {cid} in cooldown '
                    f'({remaining:.0f}s remaining)'
                )
                return False

        return True
    except Exception as e:
        logger.warning(f'Failed to check consolidation for {cid}: {e}')
        return False


# =============================================================================
# Internal: LLM call with retry and truncation handling
# =============================================================================


async def _call_consolidation_llm(
    model: str,
    user_message: str,
    max_tokens: int,
) -> dict[str, str]:
    """Call LLM for consolidation with retry on truncation.

    Retries up to 2 times with escalating max_tokens if truncated.

    Returns:
        Dict with 'history_entry' and 'memory_update' keys.

    Raises:
        ConsolidationRetryable: On transient failures (API errors).
        RuntimeError: On non-retryable failures (no tool call, parse error).
    """
    max_attempts = 3
    current_max_tokens = max_tokens

    for attempt in range(max_attempts):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {'role': 'system', 'content': _CONSOLIDATION_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_message},
                ],
                tools=[_SAVE_MEMORY_TOOL],
                tool_choice='required',
                max_tokens=current_max_tokens,
            )
        except Exception as e:
            error_str = str(e).lower()
            # Retryable: rate limits, timeouts, server errors
            if any(kw in error_str for kw in [
                'rate_limit', 'timeout', '529', '500', '502', '503',
                'overloaded', 'capacity',
            ]):
                raise ConsolidationRetryable(
                    f'Transient LLM error: {e}'
                ) from e
            # Non-retryable: auth errors, invalid requests
            raise

        finish_reason = response.choices[0].finish_reason
        message = response.choices[0].message

        # Handle truncation: retry with more tokens
        if finish_reason == 'length':
            if attempt < max_attempts - 1:
                previous = current_max_tokens
                current_max_tokens = min(current_max_tokens * 2, 8192)
                logger.warning(
                    f'Consolidation truncated (max_tokens={previous}), '
                    f'retrying with {current_max_tokens} '
                    f'(attempt {attempt + 2}/{max_attempts})'
                )
                continue
            else:
                logger.error(
                    f'Consolidation still truncated after {max_attempts} '
                    f'attempts (max_tokens={current_max_tokens})'
                )
                raise ConsolidationRetryable(
                    f'Response truncated even at max_tokens={current_max_tokens}'
                )

        # Extract tool call
        if not message.tool_calls:
            raise ConsolidationRetryable(
                'LLM did not return any tool calls'
            )

        for tc in message.tool_calls:
            if tc.function.name == 'save_memory':
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    from json_repair import repair_json
                    try:
                        args = json.loads(repair_json(tc.function.arguments))
                    except Exception:
                        raise ConsolidationRetryable(
                            f'Failed to parse tool arguments: '
                            f'{tc.function.arguments[:200]}'
                        )

                history_entry = args.get('history_entry', '')
                memory_update = args.get('memory_update', '')

                if not memory_update:
                    raise ConsolidationRetryable(
                        'LLM returned empty memory_update'
                    )

                return {
                    'history_entry': history_entry,
                    'memory_update': memory_update,
                }

        raise ConsolidationRetryable(
            'LLM called wrong tool (expected save_memory)'
        )

    # Should not reach here, but just in case
    raise ConsolidationRetryable('Max truncation retries exhausted')


# =============================================================================
# Internal: Failure tracking with cooldown
# =============================================================================


async def _record_failure(cid: str, client: Any, error: str) -> None:
    """Record a consolidation failure and set exponential cooldown."""
    try:
        failures = await client.incr(_failures_key(cid))
        await client.expire(_failures_key(cid), settings.REDIS_SESSION_TTL)

        # Exponential cooldown: 30s, 60s, 120s, 240s, 300s(cap)
        cooldown = min(
            _BASE_COOLDOWN_SECONDS * (2 ** (failures - 1)),
            _MAX_COOLDOWN_SECONDS,
        )
        cooldown_until = time.time() + cooldown
        await client.set(
            _cooldown_key(cid),
            str(cooldown_until),
            ex=int(cooldown) + 10,
        )

        logger.warning(
            f'Consolidation failed for {cid} '
            f'(failure #{failures}, cooldown {cooldown}s): {error}'
        )

        if failures >= _MAX_CONSECUTIVE_FAILURES:
            logger.error(
                f'Consolidation for {cid} has failed {failures} consecutive '
                f'times. Max cooldown ({_MAX_COOLDOWN_SECONDS}s) applied. '
                f'Check model availability and MEMORY_CONSOLIDATION_MAX_TOKENS.'
            )
    except Exception as e:
        logger.error(f'Failed to record consolidation failure for {cid}: {e}')


async def _clear_failures(cid: str, client: Any) -> None:
    """Clear failure counter and cooldown on success."""
    try:
        await client.delete(_failures_key(cid))
        await client.delete(_cooldown_key(cid))
    except Exception:
        pass  # Best effort


# =============================================================================
# Main consolidation function
# =============================================================================


async def consolidate(cid: str) -> None:
    """Run LLM-driven memory consolidation for a conversation.

    Resilience:
    - Retries LLM call up to 3x with exponential backoff on transient errors
    - Auto-escalates max_tokens on truncation
    - Circuit breaker stops calls if LLM is consistently failing
    - Exponential cooldown between failed attempts (30s → 300s)
    - Counter only resets on success
    """
    from app.storage import get_message_history, get_redis

    client = await get_redis()
    if client is None:
        return

    t0 = time.perf_counter()

    # Check circuit breaker before doing any work
    if _consolidation_breaker.is_open:
        logger.warning(
            f'Consolidation circuit breaker is OPEN, skipping {cid}'
        )
        record_consolidation('circuit_breaker_rejected')
        return

    try:
        # Get existing facts
        existing_facts = await client.get(_facts_key(cid)) or ''

        # Get recent message history for consolidation
        history = await get_message_history(
            cid, limit=settings.MEMORY_WINDOW * 2
        )
        if not history:
            return

        # Format messages for the consolidation LLM
        formatted_messages = []
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if content:
                formatted_messages.append(f'[{role}]: {content}')

        recent_text = '\n'.join(formatted_messages)

        # Build consolidation prompt
        user_message = (
            f'## EXISTING MEMORY\n{existing_facts or "(empty - new conversation)"}'
            f'\n\n## RECENT MESSAGES\n{recent_text}'
        )

        # Determine consolidation model
        model_id = (
            settings.MEMORY_CONSOLIDATION_MODEL or settings.DEFAULT_MODEL
        )
        from app.agent import get_litellm_model

        model = get_litellm_model(model_id)

        # Call LLM with retry + circuit breaker
        result = await _call_with_retry_and_breaker(
            cid, model, user_message
        )

        # Save results to Redis
        memory_update = result['memory_update']
        history_entry = result['history_entry']

        if memory_update:
            await client.set(
                _facts_key(cid),
                memory_update,
                ex=settings.REDIS_SESSION_TTL,
            )

        if history_entry:
            await client.rpush(_log_key(cid), history_entry)
            await client.expire(
                _log_key(cid), settings.REDIS_SESSION_TTL
            )

        # Reset unconsolidated counter (only on success!)
        await client.set(
            _unconsolidated_key(cid), 0,
            ex=settings.REDIS_SESSION_TTL,
        )

        # Clear failure tracking
        await _clear_failures(cid, client)

        duration = time.perf_counter() - t0
        record_consolidation('completed', duration)
        logger.info(
            f'Memory consolidated for {cid}: '
            f'{len(memory_update)} chars facts, '
            f'log entry: {history_entry[:80]}...'
        )

    except CircuitBreakerOpen:
        record_consolidation('circuit_breaker_rejected')
        logger.warning(
            f'Consolidation circuit breaker OPEN for {cid}, '
            f'will retry after recovery timeout'
        )

    except Exception as e:
        duration = time.perf_counter() - t0
        record_consolidation('failed', duration)
        await _record_failure(cid, client, str(e))


async def _call_with_retry_and_breaker(
    cid: str,
    model: str,
    user_message: str,
) -> dict[str, str]:
    """Call the consolidation LLM with retry, backoff, and circuit breaker.

    Retry strategy:
    - Up to 3 attempts with exponential backoff (1s, 2s, 4s)
    - Circuit breaker wraps each attempt
    - Truncation retries are handled inside _call_consolidation_llm

    Returns:
        Dict with 'history_entry' and 'memory_update'.
    """
    max_retries = 3
    last_error: Exception | None = None

    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = min(2 ** attempt, 8)
            logger.info(
                f'Consolidation retry {attempt + 1}/{max_retries} for {cid} '
                f'in {wait_time}s'
            )
            await asyncio.sleep(wait_time)

        try:
            async with _consolidation_breaker:
                return await _call_consolidation_llm(
                    model=model,
                    user_message=user_message,
                    max_tokens=settings.MEMORY_CONSOLIDATION_MAX_TOKENS,
                )
        except CircuitBreakerOpen:
            raise  # Don't retry, propagate immediately
        except ConsolidationRetryable as e:
            last_error = e
            logger.warning(
                f'Consolidation attempt {attempt + 1}/{max_retries} '
                f'failed for {cid}: {e}'
            )
            continue
        except Exception as e:
            # Non-retryable error
            raise

    # All retries exhausted
    raise last_error or RuntimeError(
        f'Consolidation failed after {max_retries} attempts'
    )


# =============================================================================
# Scheduling
# =============================================================================


def schedule_consolidation(cid: str) -> None:
    """Schedule consolidation as a background task with per-session locking."""

    async def _run():
        # Per-session lock to prevent concurrent consolidations
        if cid not in _consolidation_locks:
            _consolidation_locks[cid] = asyncio.Lock()

        lock = _consolidation_locks[cid]
        if lock.locked():
            logger.debug(f'Consolidation already running for {cid}, skipping')
            return

        async with lock:
            await consolidate(cid)

    record_consolidation('scheduled')
    task = asyncio.create_task(_run())
    _active_tasks.add(task)
    task.add_done_callback(_active_tasks.discard)


async def shutdown_consolidation(timeout: float = 10.0) -> None:
    """Wait for active consolidation tasks to complete during shutdown."""
    if not _active_tasks:
        return

    logger.info(f'Waiting for {len(_active_tasks)} consolidation tasks...')
    done, pending = await asyncio.wait(
        _active_tasks, timeout=timeout
    )
    if pending:
        logger.warning(
            f'{len(pending)} consolidation tasks did not complete in time'
        )
        for task in pending:
            task.cancel()
