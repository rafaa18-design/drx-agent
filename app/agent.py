"""Agent module using Agno framework.

This module creates and configures the AI agent following AgentBench standard.
Integrates with:
- Langfuse for observability and prompt management
- Redis for session state and cache
- PostgreSQL for persistent storage
"""

import base64
import time
from typing import Any

from agno.agent import Agent, RunOutput
from agno.media import Audio, File, Image, Video
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat

from app.config import settings
from app.langfuse_client import create_trace, flush, get_prompt
from app.models import (
    ActionTaken,
    DebugMetrics,
    FinalOutput,
    InputItem,
    LLMCall,
    Metrics,
    PromptDebug,
    RunDebugResponse,
    RunResponse,
    TrajectoryStage,
)
from app.storage import (
    add_message_to_history,
    get_postgres_db,
    get_session_state,
    update_session_state,
)
from app.tools import calculate, get_current_time


def get_model(model_id: str | None = None):
    """Get the appropriate model based on model_id."""
    model_id = model_id or settings.DEFAULT_MODEL

    if 'claude' in model_id.lower():
        return Claude(id=model_id)
    elif 'gpt' in model_id.lower() or 'o1' in model_id.lower():
        return OpenAIChat(id=model_id)
    else:
        return Claude(id=settings.DEFAULT_MODEL)


def get_agent_instructions() -> str:
    """Get agent instructions from Langfuse or fallback to config."""
    return get_prompt(
        name=settings.AGENT_PROMPT_NAME,
        fallback=settings.AGENT_INSTRUCTIONS_FALLBACK,
    )


def create_agent(
    model_id: str | None = None,
    session_id: str | None = None,
    instructions: str | None = None,
    session_state: dict[str, Any] | None = None,
) -> Agent:
    """Create an Agno agent with the specified configuration.

    Uses PostgreSQL for persistent storage and enables:
    - Chat history context
    - Tool result compression
    - Agentic state management
    """
    return Agent(
        model=get_model(model_id),
        tools=[get_current_time, calculate],
        instructions=instructions or get_agent_instructions(),
        # Database for persistent storage
        db=get_postgres_db(),
        # Session management
        session_id=session_id,
        session_state=session_state or {},
        # History and context
        add_history_to_context=True,
        num_history_runs=settings.NUM_HISTORY_RUNS,
        # Optimization
        compress_tool_results=settings.COMPRESS_TOOL_RESULTS,
        # Output
        markdown=True,
    )


def parse_multimodal_input(
    items: list[InputItem],
) -> tuple[str, list[Image], list[Audio], list[Video], list[File]]:
    """Parse multimodal input items into Agno media objects.

    Returns:
        Tuple of (text_message, images, audios, videos, files)
    """
    text_parts: list[str] = []
    images: list[Image] = []
    audios: list[Audio] = []
    videos: list[Video] = []
    files: list[File] = []

    for item in items:
        if item.type == 'text':
            text_parts.append(item.content)

        elif item.type == 'image':
            # Content is base64 encoded
            content_bytes = base64.b64decode(item.content)
            images.append(Image(content=content_bytes))

        elif item.type == 'audio':
            content_bytes = base64.b64decode(item.content)
            audio_format = 'wav'
            if item.mime_type:
                # Extract format from mime_type (e.g., audio/mp3 -> mp3)
                audio_format = item.mime_type.split('/')[-1]
            audios.append(Audio(content=content_bytes, format=audio_format))

        elif item.type == 'video':
            content_bytes = base64.b64decode(item.content)
            videos.append(Video(content=content_bytes))

        elif item.type == 'document':
            content_bytes = base64.b64decode(item.content)
            files.append(
                File(content=content_bytes, name=item.filename or 'document')
            )

    text_message = '\n'.join(text_parts) if text_parts else ''
    return text_message, images, audios, videos, files


def extract_actions_from_response(response: RunOutput) -> list[ActionTaken]:
    """Extract tool calls from the agent response."""
    actions = []
    if hasattr(response, 'tools') and response.tools:
        for tool_call in response.tools:
            actions.append(
                ActionTaken(
                    tool=tool_call.get('name', 'unknown'),
                    success=tool_call.get('success', True),
                    error=tool_call.get('error'),
                )
            )
    return actions


async def run_agent(
    conversation_id: str,
    items: list[InputItem],
    model: str | None = None,
) -> RunResponse:
    """Run the agent in production mode.

    Args:
        conversation_id: Unique conversation identifier
        items: List of input items (multimodal)
        model: Optional model override

    Returns:
        RunResponse with final output and metrics
    """
    start_time = time.perf_counter()

    # Get agent instructions from Langfuse
    instructions = get_agent_instructions()

    # Create Langfuse trace
    trace = create_trace(
        name='agent-run',
        session_id=conversation_id,
        metadata={
            'model': model or settings.DEFAULT_MODEL,
            'module_id': settings.MODULE_ID,
        },
        tags=['production', 'run'],
    )

    # Get session state from Redis
    session_state = await get_session_state(conversation_id)

    # Parse multimodal input
    text_message, images, audios, videos, files = parse_multimodal_input(items)

    # Create agent with session state
    agent = create_agent(
        model_id=model,
        session_id=conversation_id,
        instructions=instructions,
        session_state=session_state,
    )

    # Build run kwargs for multimodal content
    run_kwargs: dict[str, Any] = {}
    if images:
        run_kwargs['images'] = images
    if audios:
        run_kwargs['audio'] = audios
    if videos:
        run_kwargs['videos'] = videos
    if files:
        run_kwargs['files'] = files

    # Run the agent
    response: RunOutput = await agent.arun(text_message, **run_kwargs)

    # Store messages in Redis history
    await add_message_to_history(conversation_id, 'user', text_message)
    await add_message_to_history(
        conversation_id, 'assistant', response.content or ''
    )

    # Update session state in Redis if changed
    if hasattr(response, 'session_state') and response.session_state:
        await update_session_state(conversation_id, response.session_state)
        session_state = response.session_state

    # Calculate metrics
    latency_ms = (time.perf_counter() - start_time) * 1000
    tokens_used = None
    if hasattr(response, 'metrics') and response.metrics:
        tokens_used = getattr(response.metrics, 'total_tokens', None)

    # Update trace with output
    if trace:
        trace.update(
            input={'message': text_message},
            output={'response': response.content or ''},
            metadata={
                'latency_ms': latency_ms,
                'tokens_used': tokens_used,
            },
        )

    # Extract actions
    actions = extract_actions_from_response(response)

    # Flush Langfuse events
    flush()

    return RunResponse(
        conversation_id=conversation_id,
        final_output=FinalOutput(
            message=response.content or '',
            state=session_state if session_state else None,
            actions_taken=actions if actions else None,
        ),
        metrics=Metrics(
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            cost_estimate=None,
        ),
    )


async def run_agent_debug(
    conversation_id: str,
    items: list[InputItem],
    model: str | None = None,
) -> RunDebugResponse:
    """Run the agent in debug mode with full trajectory.

    Args:
        conversation_id: Unique conversation identifier
        items: List of input items (multimodal)
        model: Optional model override

    Returns:
        RunDebugResponse with trajectory and extended metrics
    """
    start_time = time.perf_counter()

    # Get agent instructions from Langfuse
    instructions = get_agent_instructions()

    # Create Langfuse trace
    trace = create_trace(
        name='agent-run-debug',
        session_id=conversation_id,
        metadata={
            'model': model or settings.DEFAULT_MODEL,
            'module_id': settings.MODULE_ID,
            'debug': True,
        },
        tags=['debug', 'run_debug'],
    )

    # Get session state from Redis
    session_state = await get_session_state(conversation_id)

    # Parse multimodal input
    text_message, images, audios, videos, files = parse_multimodal_input(items)

    # Create agent with session state
    agent = create_agent(
        model_id=model,
        session_id=conversation_id,
        instructions=instructions,
        session_state=session_state,
    )

    # Build run kwargs for multimodal content
    run_kwargs: dict[str, Any] = {}
    if images:
        run_kwargs['images'] = images
    if audios:
        run_kwargs['audio'] = audios
    if videos:
        run_kwargs['videos'] = videos
    if files:
        run_kwargs['files'] = files

    # Run the agent
    response: RunOutput = await agent.arun(text_message, **run_kwargs)

    # Store messages in Redis history
    await add_message_to_history(conversation_id, 'user', text_message)
    await add_message_to_history(
        conversation_id, 'assistant', response.content or ''
    )

    # Update session state in Redis if changed
    if hasattr(response, 'session_state') and response.session_state:
        await update_session_state(conversation_id, response.session_state)
        session_state = response.session_state

    # Calculate metrics
    latency_ms = (time.perf_counter() - start_time) * 1000

    # Extract token info
    input_tokens = 0
    output_tokens = 0
    if hasattr(response, 'metrics') and response.metrics:
        input_tokens = getattr(response.metrics, 'input_tokens', 0) or 0
        output_tokens = getattr(response.metrics, 'output_tokens', 0) or 0

    # Update trace with output
    if trace:
        trace.update(
            input={'message': text_message},
            output={'response': response.content or ''},
            metadata={
                'latency_ms': latency_ms,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
            },
        )

    # Build trajectory (single stage for monolithic agent)
    trajectory = [
        TrajectoryStage(
            stage_id='main',
            type='agent',
            sequence=1,
            prompt_debug=PromptDebug(
                final_system_prompt_used=instructions,
            ),
            llm_calls=[
                LLMCall(
                    model=model or settings.DEFAULT_MODEL,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            ],
            latency_ms=latency_ms,
        )
    ]

    # Extract actions
    actions = extract_actions_from_response(response)

    # Flush Langfuse events
    flush()

    return RunDebugResponse(
        conversation_id=conversation_id,
        final_output=FinalOutput(
            message=response.content or '',
            state=session_state if session_state else None,
            actions_taken=actions if actions else None,
        ),
        trajectory=trajectory,
        metrics=DebugMetrics(
            total_latency_ms=latency_ms,
            total_tokens={'input': input_tokens, 'output': output_tokens},
            llm_calls=1,
        ),
    )
