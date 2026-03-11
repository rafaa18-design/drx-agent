"""AgentBench Standard routes: /metadata, /run, /run_debug."""

import base64
import tempfile
import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter

from app.agent import (
    AgentResponse,
    build_system_messages,
    get_litellm_model,
    get_tools_registry,
    run_agent_loop,
)
from app.config import settings
from app.models import (
    ActionTaken,
    Capabilities,
    DebugMetrics,
    DynamicPromptMapping,
    DynamicPrompts,
    FinalOutput,
    InputItem,
    InputTypes,
    LLMCall,
    MetadataResponse,
    Metrics,
    Pipeline,
    PipelineStage,
    PromptDebug,
    RunDebugResponse,
    RunRequest,
    RunResponse,
    ToolExposed,
    TrajectoryStage,
)
from app.observability import get_logger
from app.prompt_manager import compile_prompt, get_agent_instructions, get_prompt_manager
from app.runtime import RunContext
from app.storage import (
    add_message_to_history,
    get_message_history,
    get_session_state,
    update_session_state,
)
from app.tools import formatar_contexto_completo

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def extract_response_text(response: AgentResponse) -> str:
    """Extract text from AgentResponse."""
    return response.content or ''


def transcribe_audio(audio_bytes: bytes, mime_type: str | None = None) -> str:
    """Transcribe audio to text using OpenAI Whisper API."""
    import httpx

    ext = '.mp3'
    if mime_type:
        ext_map = {'audio/ogg': '.ogg', 'audio/mpeg': '.mp3', 'audio/wav': '.wav'}
        ext = ext_map.get(mime_type, '.mp3')

    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as f:
        f.write(audio_bytes)
        f.flush()
        with open(f.name, 'rb') as audio_file:
            resp = httpx.post(
                'https://api.openai.com/v1/audio/transcriptions',
                headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}'},
                files={'file': (f'audio{ext}', audio_file)},
                data={'model': 'gpt-4o-mini-transcribe', 'language': 'pt'},
                timeout=30.0,
            )
            if resp.status_code == 200:
                return resp.json().get('text', '')
            logger.error(
                'Whisper transcription failed: status=%s body=%s',
                resp.status_code,
                resp.text[:300],
            )
            return '[audio não transcrito]'


def parse_multimodal_input(
    items: list[InputItem],
) -> tuple[str, list[dict]]:
    """Parse multimodal input items into litellm content parts.

    Returns:
        Tuple of (text_message, image_content_parts).
    """
    text_parts: list[str] = []
    images: list[dict] = []

    for item in items:
        if item.type == 'text':
            text_parts.append(item.content)
        elif item.type == 'image':
            content_bytes = base64.b64decode(item.content)
            b64_str = base64.b64encode(content_bytes).decode('utf-8')
            mime = item.mime_type or 'image/jpeg'
            images.append({
                'type': 'image_url',
                'image_url': {'url': f'data:{mime};base64,{b64_str}'},
            })
        elif item.type == 'audio':
            content_bytes = base64.b64decode(item.content)
            # Transcribe audio to text (most models don't support native audio input)
            transcription = transcribe_audio(content_bytes, item.mime_type)
            if transcription:
                text_parts.append(f'[Audio do usuário]: {transcription}')
        elif item.type == 'video':
            # Video not natively supported by text LLMs, add as note
            text_parts.append('[Vídeo enviado pelo usuário - não suportado para análise direta]')
        elif item.type == 'document':
            # Document not natively supported, add as note
            text_parts.append(
                f'[Documento enviado: {item.filename or "documento"}]'
            )

    text_message = '\n'.join(text_parts) if text_parts else ''
    return text_message, images


def extract_actions_from_response(response: AgentResponse) -> list[ActionTaken]:
    """Extract tool calls from the AgentResponse."""
    actions = []
    for tool_name in response.tools_used:
        actions.append(
            ActionTaken(
                tool=tool_name,
                success=True,
                error=None,
            )
        )
    return actions


@dataclass
class AgentRunResult:
    """Result from agent execution."""

    response: AgentResponse | None
    instructions: str
    session_state: dict[str, Any]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    text_message: str
    actions: list[ActionTaken]
    error: Exception | None = None


async def execute_agent(
    request: RunRequest,
    debug: bool = False,
) -> AgentRunResult:
    """Execute agent and return unified result."""
    from app.audit import (
        audit_agent_run_failure,
        audit_agent_run_start,
        audit_agent_run_success,
    )
    from app.memory import (
        get_memory_context,
        increment_unconsolidated,
        schedule_consolidation,
        should_consolidate,
    )

    start_time = time.perf_counter()
    conversation_id = request.conversation_id
    model_id = request.model or settings.DEFAULT_MODEL
    error: Exception | None = None
    response: AgentResponse | None = None
    instructions = ''
    session_state: dict[str, Any] = {}
    text_message = ''
    input_tokens = 0
    output_tokens = 0
    actions: list[ActionTaken] = []

    try:
        # Parse multimodal input
        text_message, images = parse_multimodal_input(request.input)

        # Audit log run start
        audit_agent_run_start(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model_id,
            input_length=len(text_message),
        )

        # Get session state from Redis
        session_state = await get_session_state(conversation_id)

        t0 = time.perf_counter()
        template = await get_agent_instructions()
        t1 = time.perf_counter()
        logger.info(
            f'[PERF] get_instructions: {(t1-t0)*1000:.0f}ms',
            extra={'request_id': ''},
        )

        # Get memory context (consolidated facts)
        memory_context = ''
        if settings.MEMORY_CONSOLIDATION_ENABLED:
            memory_context = await get_memory_context(conversation_id)

        # Format full context (memory + session state)
        full_context = formatar_contexto_completo(session_state, memory_context)

        instructions = compile_prompt(
            template,
            session_context=full_context,
        )

        # Build litellm model string
        model = get_litellm_model(model_id)

        # Fetch conversation history for multi-turn context
        history = await get_message_history(conversation_id)

        # Build messages
        messages = build_system_messages(
            instructions, text_message, images or None, history=history
        )

        # Create RunContext and tools registry
        run_context = RunContext(
            session_state=session_state,
            session_id=conversation_id,
            user_id=conversation_id,
        )
        registry = get_tools_registry()

        # Execute agent loop
        response = await run_agent_loop(
            messages=messages,
            tools=registry,
            run_context=run_context,
            model=model,
            max_iterations=settings.MAX_TURNS,
            max_tokens=settings.MAX_OUTPUT_TOKENS,
            langfuse_metadata={
                'session_id': conversation_id,
                'trace_user_id': conversation_id,
                'trace_name': f'{settings.MODULE_NAME}-run',
                'tags': [settings.MODULE_NAME, model_id],
            },
        )

        # Store messages in Redis
        response_text = extract_response_text(response)
        await add_message_to_history(conversation_id, 'user', text_message)
        await add_message_to_history(
            conversation_id, 'assistant', response_text
        )

        # Update session state from RunContext (tools may have modified it)
        if response.session_state:
            await update_session_state(
                conversation_id, response.session_state
            )
            session_state = response.session_state

        # Token info
        input_tokens = response.input_tokens
        output_tokens = response.output_tokens

        actions = extract_actions_from_response(response)

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Memory consolidation (increment twice: 1 for user msg, 1 for assistant msg)
        if settings.MEMORY_CONSOLIDATION_ENABLED:
            await increment_unconsolidated(conversation_id)
            await increment_unconsolidated(conversation_id)
            if await should_consolidate(conversation_id):
                schedule_consolidation(conversation_id)

        # Audit log success
        audit_agent_run_success(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model_id,
            duration_ms=latency_ms,
            tokens_used=input_tokens + output_tokens,
            tool_calls=len(actions),
        )

    except Exception as e:
        error = e
        logger.error(f'Agent run failed for {conversation_id}: {e}')
        latency_ms = (time.perf_counter() - start_time) * 1000
        audit_agent_run_failure(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model_id,
            error=str(e),
            duration_ms=latency_ms,
        )

    latency_ms = (time.perf_counter() - start_time) * 1000

    return AgentRunResult(
        response=response,
        instructions=instructions,
        session_state=session_state,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        text_message=text_message,
        actions=actions,
        error=error,
    )


# ---------------------------------------------------------------------------
# Tools metadata cache
# ---------------------------------------------------------------------------

_cached_tools_metadata: list[ToolExposed] | None = None


def _get_tools_metadata() -> list[ToolExposed]:
    """Return cached tool metadata for the /metadata endpoint."""
    global _cached_tools_metadata
    if _cached_tools_metadata is not None:
        return _cached_tools_metadata

    registry = get_tools_registry()
    tools = []
    for tool_def in registry._tools.values():
        params = tool_def.parameters.get('properties', {})
        parameters_schema = None
        if params:
            parameters_schema = {
                k: v.get('type', 'any') for k, v in params.items()
            }
        tools.append(
            ToolExposed(
                name=tool_def.name,
                description=tool_def.description,
                parameters_schema=parameters_schema,
            )
        )

    _cached_tools_metadata = tools
    return tools


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

agentbench_router = APIRouter(tags=['AgentBench'])


@agentbench_router.get('/metadata', response_model=MetadataResponse)
async def get_metadata() -> MetadataResponse:
    """Return module metadata following AgentBench standard."""
    pipeline = Pipeline(
        is_monolithic=True,
        stages=[
            PipelineStage(
                id='main', type='agent', model_configurable=True
            )
        ],
    )
    dynamic_prompts = DynamicPrompts(
        state_key='mode',
        mapping=[
            DynamicPromptMapping(
                state_value='default',
                base_system_prompt=settings.AGENT_INSTRUCTIONS_FALLBACK,
                expected_context_keys=['user_profile'],
            ),
        ],
    )

    return MetadataResponse(
        module_id=settings.MODULE_ID,
        version=settings.MODULE_VERSION,
        description=settings.MODULE_DESCRIPTION,
        capabilities=Capabilities(
            supports_multi_stage=False,
            supports_dynamic_system_prompt=True,
            supports_cross_model=True,
            supports_jailbreak_tests=True,
        ),
        pipeline=pipeline,
        dynamic_prompts=dynamic_prompts,
        tools_exposed=_get_tools_metadata(),
        input_types=InputTypes(
            supported_types=['text', 'image', 'audio'],
            allowed_formats={
                'image': ['jpeg', 'jpg', 'png', 'webp'],
                'audio': ['mp3', 'wav', 'ogg'],
            },
        ),
        models_supported=settings.MODELS_SUPPORTED,
    )


@agentbench_router.post('/run', response_model=RunResponse)
async def run(request: RunRequest) -> RunResponse:
    """Execute the agent in production mode (AgentBench standard)."""
    logger.info(f'Running agent for conversation: {request.conversation_id}')

    result = await execute_agent(request, debug=False)

    if result.error:
        return RunResponse(
            conversation_id=request.conversation_id,
            final_output=FinalOutput(
                message='An error occurred while processing your request.',
                state=None,
                actions_taken=None,
            ),
            metrics=Metrics(
                latency_ms=result.latency_ms,
                tokens_used=None,
                cost_estimate=None,
            ),
        )

    tokens_used = (
        result.input_tokens + result.output_tokens
        if result.input_tokens or result.output_tokens
        else None
    )

    message = extract_response_text(result.response) if result.response else ''

    if not message:
        logger.warning(
            'Agent response empty for %s',
            request.conversation_id,
        )

    logger.info(
        f'Agent run completed for {request.conversation_id} '
        f'in {result.latency_ms:.2f}ms'
    )

    return RunResponse(
        conversation_id=request.conversation_id,
        final_output=FinalOutput(
            message=message,
            state=result.session_state if result.session_state else None,
            actions_taken=result.actions if result.actions else None,
        ),
        metrics=Metrics(
            latency_ms=result.latency_ms,
            tokens_used=tokens_used,
            cost_estimate=None,
        ),
    )


@agentbench_router.post('/run_debug', response_model=RunDebugResponse)
async def run_debug(request: RunRequest) -> RunDebugResponse:
    """Execute the agent in debug mode (AgentBench standard)."""
    logger.info(
        f'Running agent (debug) for conversation: {request.conversation_id}'
    )

    result = await execute_agent(request, debug=True)

    if result.error:
        return RunDebugResponse(
            conversation_id=request.conversation_id,
            final_output=FinalOutput(
                message=f'An error occurred: {str(result.error)}',
                state=None,
                actions_taken=None,
            ),
            trajectory=[
                TrajectoryStage(
                    stage_id='error',
                    type='agent',
                    sequence=1,
                    prompt_debug=PromptDebug(
                        final_system_prompt_used='Error occurred',
                    ),
                    llm_calls=[],
                    latency_ms=result.latency_ms,
                    errors=[str(result.error)],
                )
            ],
            metrics=DebugMetrics(
                total_latency_ms=result.latency_ms,
                total_tokens={'input': 0, 'output': 0},
                llm_calls=0,
            ),
        )

    message = extract_response_text(result.response) if result.response else ''

    # Build trajectory
    trajectory = [
        TrajectoryStage(
            stage_id='main',
            type='agent',
            sequence=1,
            prompt_debug=PromptDebug(
                final_system_prompt_used=result.instructions,
            ),
            llm_calls=[
                LLMCall(
                    model=request.model or settings.DEFAULT_MODEL,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
            ],
            latency_ms=result.latency_ms,
        )
    ]
    llm_calls_count = 1

    logger.info(
        f'Agent debug run completed for {request.conversation_id} '
        f'in {result.latency_ms:.2f}ms'
    )

    return RunDebugResponse(
        conversation_id=request.conversation_id,
        final_output=FinalOutput(
            message=message,
            state=result.session_state if result.session_state else None,
            actions_taken=result.actions if result.actions else None,
        ),
        trajectory=trajectory,
        metrics=DebugMetrics(
            total_latency_ms=result.latency_ms,
            total_tokens={
                'input': result.input_tokens,
                'output': result.output_tokens,
            },
            llm_calls=llm_calls_count,
        ),
    )
