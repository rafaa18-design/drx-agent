"""Langfuse integration for observability and prompt management.

This module provides:
- Tracing and observability via OpenTelemetry
- Prompt management with versioning and caching
"""

import logging
from typing import Any

from langfuse import Langfuse

from app.config import settings

logger = logging.getLogger(__name__)

# Global Langfuse client
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


def get_prompt(
    name: str,
    fallback: str | None = None,
    variables: dict[str, Any] | None = None,
    label: str = 'production',
) -> str:
    """Fetch a prompt from Langfuse and compile it with variables.

    Args:
        name: The prompt name in Langfuse
        fallback: Fallback prompt if Langfuse is unavailable
        variables: Variables to compile into the prompt template
        label: The label to fetch (default: production)

    Returns:
        The compiled prompt string
    """
    langfuse = get_langfuse()

    if langfuse is None:
        logger.debug(
            f'Langfuse not available, using fallback for prompt: {name}'
        )
        return fallback or ''

    try:
        prompt = langfuse.get_prompt(name, label=label)
        if variables:
            return prompt.compile(**variables)
        return prompt.compile()
    except Exception as e:
        logger.warning(f'Failed to fetch prompt "{name}" from Langfuse: {e}')
        return fallback or ''


def get_chat_prompt(
    name: str,
    fallback: list[dict[str, str]] | None = None,
    variables: dict[str, Any] | None = None,
    label: str = 'production',
) -> list[dict[str, str]]:
    """Fetch a chat prompt from Langfuse and compile it with variables.

    Args:
        name: The prompt name in Langfuse
        fallback: Fallback messages if Langfuse is unavailable
        variables: Variables to compile into the prompt template
        label: The label to fetch (default: production)

    Returns:
        List of message dictionaries with role and content
    """
    langfuse = get_langfuse()

    if langfuse is None:
        logger.debug(
            f'Langfuse not available, using fallback for prompt: {name}'
        )
        return fallback or []

    try:
        prompt = langfuse.get_prompt(name, type='chat', label=label)
        if variables:
            return prompt.compile(**variables)
        return prompt.compile()
    except Exception as e:
        logger.warning(
            f'Failed to fetch chat prompt "{name}" from Langfuse: {e}'
        )
        return fallback or []


def update_trace_metadata(
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
):
    """Update the current Langfuse trace with metadata.

    Must be called within a function decorated with @observe().
    """
    langfuse = get_langfuse()
    if langfuse is None:
        return

    try:
        langfuse.update_current_trace(
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
            tags=tags or [],
        )
    except Exception as e:
        logger.warning(f'Failed to update trace metadata: {e}')


def flush():
    """Flush all pending events to Langfuse."""
    langfuse = get_langfuse()
    if langfuse:
        try:
            langfuse.flush()
        except Exception as e:
            logger.error(f'Failed to flush Langfuse events: {e}')


def shutdown():
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
