"""Agent module using Agno framework.

This module creates and configures the AI agent for AgentOS.
Supports multiple model providers:
- Anthropic (direct API)
- OpenAI
- Vertex AI (Google Cloud)
"""

import logging

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat

from app.config import settings
from app.prompt_manager import get_agent_instructions_sync
from app.storage import get_redis_db
from app.tools import (add_to_list, calculate, check_threshold, format_date,
                       generate_uuid, get_current_time)

logger = logging.getLogger(__name__)


def get_model(model_id: str | None = None):
    """Get the appropriate model based on model_id and provider configuration.

    Supports:
    - Anthropic Claude (direct API)
    - OpenAI GPT models
    - Vertex AI Claude (Google Cloud)
    """
    model_id = model_id or settings.DEFAULT_MODEL

    # Vertex AI Claude (model IDs contain @ symbol)
    if '@' in model_id or settings.MODEL_PROVIDER == 'vertexai':
        try:
            from agno.models.vertexai.claude import Claude as VertexClaude

            return VertexClaude(
                id=model_id,
                project_id=settings.GOOGLE_CLOUD_PROJECT or None,
                region=settings.GOOGLE_CLOUD_REGION or None,
                cache_system_prompt=settings.CACHE_SYSTEM_PROMPT,
                max_tokens=settings.MAX_OUTPUT_TOKENS,
            )
        except ImportError:
            logger.warning(
                'Vertex AI not available, falling back to Anthropic direct'
            )
            # Fall through to Anthropic

    # Anthropic Claude (direct API)
    if 'claude' in model_id.lower():
        return Claude(
            id=model_id,
            api_key=settings.ANTHROPIC_API_KEY or None,
            cache_system_prompt=settings.CACHE_SYSTEM_PROMPT,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
        )

    # OpenAI models
    if 'gpt' in model_id.lower() or 'o1' in model_id.lower():
        return OpenAIChat(
            id=model_id,
            api_key=settings.OPENAI_API_KEY or None,
            max_completion_tokens=settings.MAX_OUTPUT_TOKENS,
            reasoning_effort=settings.REASONING_EFFORT,
        )

    # Default to Claude
    return Claude(
        id=settings.DEFAULT_MODEL,
        api_key=settings.ANTHROPIC_API_KEY or None,
        cache_system_prompt=settings.CACHE_SYSTEM_PROMPT,
        max_tokens=settings.MAX_OUTPUT_TOKENS,
    )


def get_agent_instructions() -> str:
    """Get agent instructions synchronously."""
    return get_agent_instructions_sync()


def create_agent(
    model_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    instructions: str | None = None,
) -> Agent:
    """Create an Agno agent with the specified configuration.

    This agent is used by AgentOS to handle requests.

    Args:
        model_id: Optional model override (defaults to settings.DEFAULT_MODEL)
        session_id: Unique session/conversation identifier
        user_id: Unique user identifier for memory management
        instructions: Operational instructions for the agent
    """
    return Agent(
        # Agent identity
        name=settings.AGENT_NAME,
        id=settings.AGENT_NAME,
        description=settings.AGENT_DESCRIPTION,
        # Model configuration
        model=get_model(model_id),
        # Tools (including examples demonstrating RetryAgentRun and StopAgentRun)
        tools=[
            get_current_time,
            calculate,
            generate_uuid,
            format_date,
            add_to_list,  # Demonstrates RetryAgentRun with session state
            check_threshold,  # Demonstrates StopAgentRun
        ],
        # Instructions (can be dynamic from Langfuse)
        instructions=instructions or get_agent_instructions(),
        # Database for session storage (Redis for low latency)
        db=get_redis_db(),
        # Session management
        session_id=session_id,
        user_id=user_id,
        # History and context management
        add_history_to_context=True,
        num_history_runs=settings.NUM_HISTORY_RUNS,
        # Memory features
        enable_user_memories=settings.ENABLE_USER_MEMORIES,
        enable_session_summaries=settings.ENABLE_SESSION_SUMMARIES,
        # Optimization
        compress_tool_results=settings.COMPRESS_TOOL_RESULTS,
        tool_call_limit=settings.TOOL_CALL_LIMIT,
        # Output formatting
        markdown=True,
    )


def get_configured_agent() -> Agent:
    """Get a pre-configured agent instance for AgentOS.

    This is the main entry point used by AgentOS.
    """
    return create_agent()
