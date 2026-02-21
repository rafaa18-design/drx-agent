"""Prompt Manager with Redis caching and Langfuse integration.

Manages agent prompts with the following strategy:
1. Try to get prompt from Redis cache
2. If not in cache, fetch from Langfuse
3. Cache the fetched prompt in Redis
4. Support webhook updates from Langfuse (for 'latest' prompts only)
"""

import logging
import re
import time
from typing import Any

from app.config import settings
from app.langfuse_client import get_langfuse
from app.storage import get_redis

logger = logging.getLogger(__name__)

# Singleton instance
_prompt_manager: 'PromptManager | None' = None

# Cache duration for "prompt not found" state to avoid spamming logs (seconds)
_LANGFUSE_NOT_FOUND_CACHE_TTL = 300


class PromptManager:
    """Manages agent prompts with Redis caching and Langfuse fallback."""

    def __init__(self):
        self._prompt_name = settings.AGENT_PROMPT_NAME
        self._prompt_version = settings.AGENT_PROMPT_VERSION
        self._prompt_label = settings.AGENT_PROMPT_LABEL
        self._fallback = settings.AGENT_INSTRUCTIONS_FALLBACK
        self._redis_key = settings.PROMPT_REDIS_KEY
        self._redis_ttl = settings.PROMPT_REDIS_TTL
        self._langfuse_not_found_until: float = 0

    @property
    def is_versioned(self) -> bool:
        """Check if using a specific version (not latest)."""
        return self._prompt_version is not None

    async def get_prompt(self) -> str:
        """Get the current prompt, with Redis cache and Langfuse fallback.

        Returns:
            The prompt string to use for the agent.
        """
        # 1. Try Redis cache first
        cached_prompt = await self._get_prompt_from_redis()
        if cached_prompt:
            logger.debug('Prompt loaded from Redis cache')
            return cached_prompt

        # 2. Fetch from Langfuse
        prompt = self._fetch_from_langfuse()

        # 3. Cache in Redis
        if prompt:
            await self._set_prompt_in_redis(prompt)
            logger.info('Prompt fetched from Langfuse and cached in Redis')
            return prompt

        # 4. Fallback
        logger.debug(
            f'Using fallback prompt for {self._prompt_name}'
        )
        return self._fallback

    def get_prompt_sync(self) -> str:
        """Synchronous version of get_prompt for non-async contexts.

        Note: This version skips Redis and goes directly to Langfuse.
        """
        # Try Langfuse directly
        prompt = self._fetch_from_langfuse()
        if prompt:
            return prompt
        return self._fallback

    async def _get_prompt_from_redis(self) -> str | None:
        """Get prompt from Redis cache."""
        try:
            redis = await get_redis()
            if redis is None:
                return None

            # Build key based on version
            key = self._get_redis_key()
            prompt = await redis.get(key)
            if prompt:
                return (
                    prompt.decode('utf-8')
                    if isinstance(prompt, bytes)
                    else prompt
                )
            return None
        except Exception as e:
            logger.warning(f'Failed to get prompt from Redis: {e}')
            return None

    async def _set_prompt_in_redis(self, prompt: str) -> bool:
        """Set prompt in Redis cache."""
        try:
            redis = await get_redis()
            if redis is None:
                return False

            key = self._get_redis_key()
            if self._redis_ttl > 0:
                await redis.set(key, prompt, ex=self._redis_ttl)
            else:
                await redis.set(key, prompt)  # No expiry
            return True
        except Exception as e:
            logger.error(f'Failed to set prompt in Redis: {e}')
            return False

    def _get_redis_key(self) -> str:
        """Get the Redis key for the prompt."""
        if self.is_versioned:
            return f'{self._redis_key}:v{self._prompt_version}'
        return self._redis_key

    def _fetch_from_langfuse(self) -> str | None:
        """Fetch prompt from Langfuse."""
        # Skip if we recently got a "not found" to avoid spamming logs
        now = time.monotonic()
        if now < self._langfuse_not_found_until:
            return None

        langfuse = get_langfuse()
        if langfuse is None:
            logger.warning('Langfuse not available')
            return None

        try:
            # Build fetch parameters
            kwargs: dict[str, Any] = {'name': self._prompt_name}

            if self._prompt_version:
                kwargs['version'] = int(self._prompt_version)
            elif self._prompt_label:
                kwargs['label'] = self._prompt_label

            prompt_obj = langfuse.get_prompt(**kwargs)

            if prompt_obj is None:
                return None

            # Reset not-found cache on success
            self._langfuse_not_found_until = 0

            # Handle different prompt types
            if hasattr(prompt_obj, 'prompt'):
                return prompt_obj.prompt
            elif hasattr(prompt_obj, 'get_langchain_prompt'):
                # For chat prompts, get the system message
                return str(prompt_obj.get_langchain_prompt())
            else:
                return str(prompt_obj)

        except Exception as e:
            # Cache "not found" errors to avoid logging on every request
            if '404' in str(e) or 'NotFound' in str(e):
                self._langfuse_not_found_until = now + _LANGFUSE_NOT_FOUND_CACHE_TTL
                logger.warning(
                    f'Prompt "{self._prompt_name}" not found in Langfuse, '
                    f'will use fallback for {_LANGFUSE_NOT_FOUND_CACHE_TTL}s before retrying'
                )
            else:
                logger.error(f'Failed to fetch prompt from Langfuse: {e}')
            return None

    async def update_prompt_from_webhook(self, prompt_text: str) -> bool:
        """Update prompt from webhook (only for 'latest' prompts).

        Args:
            prompt_text: The new prompt text from webhook

        Returns:
            True if updated, False if ignored (versioned) or failed
        """
        if self.is_versioned:
            logger.info(
                f'Ignoring webhook update - using versioned prompt v{self._prompt_version}'
            )
            return False

        # Check if prompt is different
        current = await self._get_prompt_from_redis()
        if current == prompt_text:
            logger.info(
                'Webhook prompt identical to cached - no update needed'
            )
            return True

        # Update Redis
        success = await self._set_prompt_in_redis(prompt_text)
        if success:
            logger.info('Prompt updated from webhook')
        return success

    async def invalidate_cache(self) -> bool:
        """Invalidate the cached prompt, forcing a refresh from Langfuse."""
        try:
            redis = await get_redis()
            if redis is None:
                return False

            key = self._get_redis_key()
            await redis.delete(key)
            logger.info('Prompt cache invalidated')
            return True
        except Exception as e:
            logger.error(f'Failed to invalidate prompt cache: {e}')
            return False


def get_prompt_manager() -> PromptManager:
    """Get the singleton PromptManager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


async def get_agent_instructions() -> str:
    """Get agent instructions using the PromptManager.

    This is the main function to call from the agent module.
    """
    manager = get_prompt_manager()
    return await manager.get_prompt()


def get_agent_instructions_sync() -> str:
    """Synchronous version for non-async contexts."""
    manager = get_prompt_manager()
    return manager.get_prompt_sync()


def compile_prompt(template: str, **variables: str) -> str:
    """Compile a prompt template by replacing {{variable}} placeholders.

    Follows the same convention as Langfuse text prompts.
    Variables not provided are replaced with empty string.

    Args:
        template: Prompt template with {{variable}} placeholders.
        **variables: Key-value pairs to substitute.

    Returns:
        Compiled prompt string.
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        return variables.get(key, '')

    return re.sub(r'\{\{(\s*\w+\s*)\}\}', replacer, template)
