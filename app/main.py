"""Asani AI Agent Template - AgentOS with AgentBench Standard.

This module sets up an AgentOS instance with:
- AgentBench Standard endpoints (/metadata, /run, /run_debug)
- JWT authentication via Agno's built-in middleware
- Custom FastAPI routes for prompt management
- PostgreSQL for persistent storage
- Redis for caching
- Langfuse for observability
- Rate limiting and request tracing
"""

import base64
import hashlib
import hmac
import inspect
import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from agno.agent import RunOutput
from agno.media import Audio, File, Image, Video
from agno.os import AgentOS
from agno.os.middleware.jwt import JWTMiddleware
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.agent import create_agent, get_configured_agent
from app.auth import (authenticate_user, get_scopes_from_token,
                      has_required_scope)
from app.config import settings
from langfuse import observe

from app.langfuse_client import flush, get_langfuse, update_trace_metadata
from app.langfuse_client import shutdown as langfuse_shutdown
from app.logging_config import get_logger, request_id_var, setup_logging

# Setup logging early (must be before other app imports)
setup_logging()

from app.models import DebugMetrics  # noqa: E402
from app.models import (ActionTaken, Capabilities, DynamicPromptMapping,
                        DynamicPrompts, FinalOutput, InputItem, InputTypes,
                        LLMCall, MetadataResponse, Metrics, Pipeline,
                        PipelineStage, PromptDebug, RunDebugResponse,
                        RunRequest, RunResponse, ToolExposed, TrajectoryStage)
from app.prompt_manager import get_agent_instructions  # noqa: E402
from app.prompt_manager import get_prompt_manager
from app.storage import close_redis  # noqa: E402
from app.storage import (add_message_to_history, get_postgres_db, get_redis,
                         get_session_state, update_session_state)
from app.tools import __all__ as tool_names  # noqa: E402
from app.tools import check_threshold  # noqa: E402
from app.tools import (add_to_list, calculate, format_date, generate_uuid,
                       get_current_time)

logger = get_logger(__name__)


# =============================================================================
# Request ID Middleware
# =============================================================================


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.state.request_id = request_id

        # Set request ID in context var for logging
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers['X-Request-ID'] = request_id
            return response
        finally:
            request_id_var.reset(token)


# =============================================================================
# Rate Limiting Middleware
# =============================================================================


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware.

    For production, consider using Redis-based rate limiting.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = {}

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
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
                return f"user:{payload.get('sub', 'unknown')}"
            except Exception:
                pass

        # Fall back to IP address
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f'ip:{request.client.host if request.client else "unknown"}'

    def _is_rate_limited(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit."""
        now = time.time()
        window_start = now - 60  # 1 minute window

        # Clean old requests
        if client_id in self.requests:
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > window_start
            ]
        else:
            self.requests[client_id] = []

        # Check limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return True

        # Record request
        self.requests[client_id].append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check
        if request.url.path in ['/', '/health', '/docs', '/openapi.json']:
            return await call_next(request)

        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client_id = self._get_client_id(request)

        if self._is_rate_limited(client_id):
            logger.warning(f'Rate limit exceeded for {client_id}')
            return JSONResponse(
                status_code=429,
                content={
                    'detail': 'Rate limit exceeded. Please try again later.',
                    'retry_after': 60,
                },
                headers={'Retry-After': '60'},
            )

        return await call_next(request)


# =============================================================================
# Application Lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler with graceful shutdown."""
    import asyncio

    from app.tracing import setup_tracing, shutdown_tracing

    # Startup
    setup_tracing(app)
    get_langfuse()
    try:
        await get_redis()
        logger.info('Redis connected')
    except Exception as e:
        logger.warning(f'Redis not available: {e}')

    # Pre-load prompt into cache
    try:
        manager = get_prompt_manager()
        prompt = await manager.get_prompt()
        logger.info(f'Prompt loaded: {len(prompt)} characters')
    except Exception as e:
        logger.warning(f'Failed to pre-load prompt: {e}')

    logger.info('Application startup complete')

    yield

    # Graceful shutdown
    logger.info('Initiating graceful shutdown...')
    shutdown_start = asyncio.get_event_loop().time()
    timeout = settings.SHUTDOWN_TIMEOUT

    # Wait for in-flight requests to complete
    # The middleware tracks active requests via metrics
    try:
        from app.metrics import get_active_requests

        while get_active_requests() > 0:
            elapsed = asyncio.get_event_loop().time() - shutdown_start
            if elapsed >= timeout:
                logger.warning(
                    f'Shutdown timeout ({timeout}s) reached with '
                    f'{get_active_requests()} requests still in-flight'
                )
                break
            logger.info(
                f'Waiting for {get_active_requests()} in-flight requests... '
                f'({int(timeout - elapsed)}s remaining)'
            )
            await asyncio.sleep(1)
    except ImportError:
        # Metrics not available, just wait a bit
        await asyncio.sleep(2)

    # Cleanup resources
    shutdown_tracing()
    await close_redis()
    langfuse_shutdown()
    logger.info('Application shutdown complete')


# =============================================================================
# Custom FastAPI Application
# =============================================================================

custom_app = FastAPI(
    title=settings.MODULE_DESCRIPTION,
    version=settings.MODULE_VERSION,
    lifespan=lifespan,
)


# =============================================================================
# Helper Functions for Agent Execution
# =============================================================================


def parse_multimodal_input(
    items: list[InputItem],
) -> tuple[str, list[Image], list[Audio], list[Video], list[File]]:
    """Parse multimodal input items into Agno media objects."""
    text_parts: list[str] = []
    images: list[Image] = []
    audios: list[Audio] = []
    videos: list[Video] = []
    files: list[File] = []

    for item in items:
        if item.type == 'text':
            text_parts.append(item.content)
        elif item.type == 'image':
            content_bytes = base64.b64decode(item.content)
            images.append(Image(content=content_bytes))
        elif item.type == 'audio':
            content_bytes = base64.b64decode(item.content)
            audio_format = 'wav'
            if item.mime_type:
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
        for tool_execution in response.tools:
            success = (
                not hasattr(tool_execution, 'error')
                or tool_execution.error is None
            )
            error_msg = None
            if hasattr(tool_execution, 'error') and tool_execution.error:
                error_msg = str(tool_execution.error)
            actions.append(
                ActionTaken(
                    tool=getattr(tool_execution, 'tool_name', 'unknown'),
                    success=success,
                    error=error_msg,
                )
            )
    return actions


@dataclass
class AgentRunResult:
    """Result from agent execution."""

    response: RunOutput
    instructions: str
    session_state: dict[str, Any]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    text_message: str
    actions: list[ActionTaken]
    error: Exception | None = None


@observe(name='agent-run')
async def execute_agent(
    request: RunRequest,
    debug: bool = False,
) -> AgentRunResult:
    """Execute agent and return unified result.

    This is the core agent execution logic shared by /run and /run_debug.

    Args:
        request: The run request with input and configuration.
        debug: Whether this is a debug run (affects logging tags).

    Returns:
        AgentRunResult with all execution details.
    """
    from app.audit import (audit_agent_run_failure, audit_agent_run_start,
                           audit_agent_run_success)

    start_time = time.perf_counter()
    conversation_id = request.conversation_id
    model = request.model or settings.DEFAULT_MODEL
    error: Exception | None = None
    response: RunOutput | None = None
    instructions = ''
    session_state: dict[str, Any] = {}
    text_message = ''
    input_tokens = 0
    output_tokens = 0
    actions: list[ActionTaken] = []

    # Update Langfuse trace metadata
    update_trace_metadata(
        user_id=conversation_id,
        session_id=conversation_id,
        metadata={
            'model': model,
            'module_id': settings.MODULE_ID,
            'debug': debug,
        },
        tags=['debug' if debug else 'production', 'agentbench'],
    )

    try:
        # Get agent instructions
        t0 = time.perf_counter()
        instructions = await get_agent_instructions()
        t1 = time.perf_counter()
        logger.info(f'[PERF] get_instructions: {(t1-t0)*1000:.0f}ms', extra={'request_id': ''})

        # Get session state from Redis
        session_state = await get_session_state(conversation_id)
        t2 = time.perf_counter()
        logger.info(f'[PERF] get_session_state: {(t2-t1)*1000:.0f}ms', extra={'request_id': ''})

        # Parse multimodal input
        text_message, images, audios, videos, files = parse_multimodal_input(
            request.input
        )

        # Audit log run start
        audit_agent_run_start(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model,
            input_length=len(text_message),
        )

        # Create agent
        agent = create_agent(
            model_id=request.model,
            session_id=conversation_id,
            user_id=conversation_id,
            instructions=instructions,
        )
        t3 = time.perf_counter()
        logger.info(f'[PERF] create_agent: {(t3-t2)*1000:.0f}ms', extra={'request_id': ''})

        # Build run kwargs
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
        response = await agent.arun(text_message, **run_kwargs)
        t4 = time.perf_counter()
        logger.info(f'[PERF] agent.arun: {(t4-t3)*1000:.0f}ms', extra={'request_id': ''})

        # Store messages in Redis
        await add_message_to_history(conversation_id, 'user', text_message)
        await add_message_to_history(
            conversation_id, 'assistant', response.content or ''
        )

        # Update session state
        if hasattr(response, 'session_state') and response.session_state:
            await update_session_state(conversation_id, response.session_state)
            session_state = response.session_state

        # Extract token info
        if hasattr(response, 'metrics') and response.metrics:
            input_tokens = getattr(response.metrics, 'input_tokens', 0) or 0
            output_tokens = getattr(response.metrics, 'output_tokens', 0) or 0

        # Extract actions
        actions = extract_actions_from_response(response)

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Flush Langfuse
        flush()

        # Audit log success
        audit_agent_run_success(
            user_id=conversation_id,
            session_id=conversation_id,
            model=model,
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
            model=model,
            error=str(e),
            duration_ms=latency_ms,
        )

    latency_ms = (time.perf_counter() - start_time) * 1000

    return AgentRunResult(
        response=response,  # type: ignore
        instructions=instructions,
        session_state=session_state,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        text_message=text_message,
        actions=actions,
        error=error,
    )


# =============================================================================
# AgentBench Standard Routes
# =============================================================================

agentbench_router = APIRouter(tags=['AgentBench'])

# Registry of tools for introspection
_TOOLS_REGISTRY = {
    'get_current_time': get_current_time,
    'calculate': calculate,
    'generate_uuid': generate_uuid,
    'format_date': format_date,
    'add_to_list': add_to_list,
    'check_threshold': check_threshold,
}


def _get_tools_metadata() -> list[ToolExposed]:
    """Dynamically discover and document exposed tools via introspection."""
    tools = []

    for name in tool_names:
        tool_func = _TOOLS_REGISTRY.get(name)
        description = f'Tool: {name}'
        parameters_schema: dict[str, str] | None = None

        if tool_func:
            # Get docstring
            if hasattr(tool_func, 'func'):
                # Agno Function wrapper
                actual_func = tool_func.func
            elif hasattr(tool_func, 'entrypoint'):
                actual_func = tool_func.entrypoint
            else:
                actual_func = tool_func

            # Extract description from docstring
            if actual_func.__doc__:
                doc_lines = actual_func.__doc__.strip().split('\n')
                description = doc_lines[0]

            # Extract parameters from signature
            try:
                sig = inspect.signature(actual_func)
                params = {}
                for param_name, param in sig.parameters.items():
                    if param_name == 'run_context':
                        continue  # Skip RunContext parameter
                    param_type = 'any'
                    if param.annotation != inspect.Parameter.empty:
                        param_type = getattr(
                            param.annotation, '__name__', str(param.annotation)
                        )
                    if param.default != inspect.Parameter.empty:
                        param_type += ' (optional)'
                    params[param_name] = param_type
                if params:
                    parameters_schema = params
            except (ValueError, TypeError):
                pass

        tools.append(
            ToolExposed(
                name=name,
                description=description,
                parameters_schema=parameters_schema,
            )
        )

    return tools


@agentbench_router.get('/metadata', response_model=MetadataResponse)
async def get_metadata() -> MetadataResponse:
    """Return module metadata following AgentBench standard.

    Declares the module's capabilities, pipeline structure,
    exposed tools, and supported input types.
    """
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
        pipeline=Pipeline(
            is_monolithic=True,
            stages=[
                PipelineStage(
                    id='main',
                    type='agent',
                    model_configurable=True,
                )
            ],
        ),
        dynamic_prompts=DynamicPrompts(
            state_key='mode',
            mapping=[
                DynamicPromptMapping(
                    state_value='default',
                    base_system_prompt=settings.AGENT_INSTRUCTIONS_FALLBACK,
                    expected_context_keys=['user_profile'],
                ),
            ],
        ),
        tools_exposed=_get_tools_metadata(),
        input_types=InputTypes(
            supported_types=['text', 'image', 'audio', 'video', 'document'],
            allowed_formats={
                'image': ['jpeg', 'jpg', 'png', 'webp'],
                'audio': ['mp3', 'wav', 'ogg'],
                'video': ['mp4', 'webm'],
                'document': ['pdf', 'txt', 'md', 'json', 'docx', 'csv'],
            },
        ),
        models_supported=settings.MODELS_SUPPORTED,
    )


@agentbench_router.post('/run', response_model=RunResponse)
async def run(request: RunRequest) -> RunResponse:
    """Execute the agent in production mode (AgentBench standard).

    Processes the input and returns the final response with basic metrics.
    The module manages conversation history internally using conversation_id.
    """
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

    logger.info(
        f'Agent run completed for {request.conversation_id} '
        f'in {result.latency_ms:.2f}ms'
    )

    return RunResponse(
        conversation_id=request.conversation_id,
        final_output=FinalOutput(
            message=result.response.content or '',
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
    """Execute the agent in debug mode (AgentBench standard).

    Same as /run but includes full trajectory for observability.
    """
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
                    stage_id='main',
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

    logger.info(
        f'Agent debug run completed for {request.conversation_id} '
        f'in {result.latency_ms:.2f}ms'
    )

    return RunDebugResponse(
        conversation_id=request.conversation_id,
        final_output=FinalOutput(
            message=result.response.content or '',
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
            llm_calls=1,
        ),
    )


custom_app.include_router(agentbench_router)


# =============================================================================
# Authentication Endpoints
# =============================================================================

auth_router = APIRouter(prefix='/auth', tags=['Authentication'])


@auth_router.post('/login')
async def login(request: Request, username: str, password: str):
    """Login endpoint that returns JWT token.

    Validates credentials against AUTH_USERS configuration.
    Supports bcrypt hashed passwords (recommended) or plain text (dev only).

    Args:
        request: FastAPI request object.
        username: The username to authenticate.
        password: The password to verify.

    Returns:
        JWT access token on success.

    Raises:
        HTTPException: 401 if credentials invalid, 500 if JWT not configured.
    """
    from app.audit import audit_login_failure, audit_login_success

    client_ip = (
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    )
    if not client_ip and request.client:
        client_ip = request.client.host
    user_agent = request.headers.get('User-Agent')

    if not settings.JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail='JWT authentication not configured (set JWT_SECRET)',
        )

    if not settings.AUTH_USERS:
        raise HTTPException(
            status_code=500,
            detail='User authentication not configured (set AUTH_USERS)',
        )

    if not authenticate_user(username, password):
        logger.warning(f'Failed login attempt for user: {username}')
        audit_login_failure(
            username=username,
            reason='invalid_credentials',
            client_ip=client_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=401, detail='Invalid credentials')

    now = datetime.now(UTC)
    payload = {
        'sub': username,
        'name': username,
        'iat': now,
        'exp': now + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        'scopes': ['agents:read', 'agents:run'],
    }

    token = jwt.encode(
        payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )

    logger.info(f'Successful login for user: {username}')
    audit_login_success(
        user_id=username,
        client_ip=client_ip,
        user_agent=user_agent,
    )
    return {
        'access_token': token,
        'token_type': 'bearer',
        'expires_in': settings.JWT_EXPIRATION_HOURS * 3600,
    }


@auth_router.post('/token')
async def create_token(
    request: Request,
    user_id: str,
    scopes: list[str] | None = None,
    expires_hours: int | None = None,
):
    """Create a JWT token programmatically (admin only).

    This endpoint requires authentication with admin scopes.
    Configure AUTH_ADMIN_SCOPES to control which scopes can create tokens.

    Args:
        request: FastAPI request object (for auth extraction).
        user_id: The user ID for the new token.
        scopes: Optional scopes to assign to the token.
        expires_hours: Optional expiration time in hours.

    Returns:
        JWT access token.

    Raises:
        HTTPException: 401 if not authenticated, 403 if insufficient permissions.
    """
    from app.audit import audit_auth_denied, audit_token_created

    if not settings.JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail='JWT authentication not configured',
        )

    # Verify caller has admin privileges
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail='Authentication required to create tokens',
        )

    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        caller_scopes = get_scopes_from_token(payload)
        caller_id = payload.get('sub')

        if not has_required_scope(caller_scopes, settings.AUTH_ADMIN_SCOPES):
            logger.warning(
                f'Token creation denied - user {caller_id} '
                f'lacks required scopes: {settings.AUTH_ADMIN_SCOPES}'
            )
            audit_auth_denied(
                user_id=caller_id,
                resource='/auth/token',
                reason=f'Missing required scopes: {settings.AUTH_ADMIN_SCOPES}',
            )
            raise HTTPException(
                status_code=403,
                detail=f'Requires one of: {settings.AUTH_ADMIN_SCOPES}',
            )
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f'Invalid token: {e}')

    now = datetime.now(UTC)
    exp_hours = expires_hours or settings.JWT_EXPIRATION_HOURS

    new_payload = {
        'sub': user_id,
        'iat': now,
        'exp': now + timedelta(hours=exp_hours),
        'scopes': scopes or ['agents:read', 'agents:run'],
        'created_by': caller_id,  # Track who created the token
    }

    new_token = jwt.encode(
        new_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )

    logger.info(f'Token created for user {user_id} by {caller_id}')
    audit_token_created(
        issuer_id=caller_id,
        target_user_id=user_id,
        scopes=scopes or ['agents:read', 'agents:run'],
        expires_in=exp_hours * 3600,
    )
    return {'access_token': new_token, 'token_type': 'bearer'}


custom_app.include_router(auth_router)


# =============================================================================
# Prompt Management Endpoints
# =============================================================================

prompt_router = APIRouter(prefix='/prompt', tags=['Prompt'])


@prompt_router.post('/webhook')
async def prompt_webhook(request: Request):
    """Receive webhooks from Langfuse with prompt updates."""
    try:
        raw_body = await request.body()
        raw_body_str = raw_body.decode('utf-8')

        signature_header = request.headers.get('x-langfuse-signature')

        if settings.LANGFUSE_SIGNATURE_SECRET:
            if not signature_header:
                raise HTTPException(
                    status_code=401, detail='Signature missing'
                )

            if not _verify_langfuse_signature(
                raw_body_str,
                signature_header,
                settings.LANGFUSE_SIGNATURE_SECRET,
            ):
                raise HTTPException(
                    status_code=401, detail='Invalid signature'
                )

        data = json.loads(raw_body_str)

        if not data or 'prompt' not in data or 'prompt' not in data['prompt']:
            raise HTTPException(
                status_code=400,
                detail='Field prompt.prompt not found in payload',
            )

        prompt_text = data['prompt']['prompt']
        logger.info(
            f'Langfuse webhook: received prompt with {len(prompt_text)} chars'
        )

        manager = get_prompt_manager()
        success = await manager.update_prompt_from_webhook(prompt_text)

        if success:
            return JSONResponse(
                content={'status': 'success', 'message': 'Prompt updated'},
                status_code=200,
            )
        else:
            return JSONResponse(
                content={
                    'status': 'ignored',
                    'message': 'Using versioned prompt',
                },
                status_code=200,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f'Langfuse webhook error: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@prompt_router.post('/refresh')
async def refresh_prompt():
    """Force refresh the prompt from Langfuse."""
    manager = get_prompt_manager()
    await manager.invalidate_cache()
    prompt = await manager.get_prompt()
    return {
        'status': 'success',
        'message': 'Prompt refreshed',
        'prompt_length': len(prompt),
    }


@prompt_router.get('/current')
async def get_current_prompt():
    """Get the current prompt being used."""
    manager = get_prompt_manager()
    prompt = await manager.get_prompt()
    return {
        'prompt_length': len(prompt),
        'prompt_preview': prompt[:200] + '...'
        if len(prompt) > 200
        else prompt,
        'is_versioned': manager.is_versioned,
    }


def _verify_langfuse_signature(
    raw_body: str, signature_header: str, secret: str
) -> bool:
    """Validate Langfuse webhook signature."""
    try:
        ts_pair, sig_pair = signature_header.split(',', 1)
    except ValueError:
        return False

    if not ts_pair.startswith('t=') or not (
        sig_pair.startswith('s=') or sig_pair.startswith('v1=')
    ):
        return False

    timestamp = ts_pair.split('=', 1)[1]
    received_sig_hex = sig_pair.split('=', 1)[1]

    message = f'{timestamp}.{raw_body}'.encode('utf-8')
    expected_sig_hex = hmac.new(
        secret.encode('utf-8'), message, hashlib.sha256
    ).hexdigest()

    try:
        return hmac.compare_digest(
            bytes.fromhex(received_sig_hex), bytes.fromhex(expected_sig_hex)
        )
    except ValueError:
        return False


custom_app.include_router(prompt_router)


# =============================================================================
# System Endpoints
# =============================================================================

system_router = APIRouter(tags=['System'])


@system_router.get('/health')
async def health():
    """Health check endpoint with dependency status."""
    from app.storage import get_redis, is_redis_available

    status = 'ok'
    dependencies = {}

    # Check Redis
    try:
        redis_client = await get_redis()
        if redis_client:
            await redis_client.ping()
            dependencies['redis'] = {'status': 'ok'}
        elif not is_redis_available():
            dependencies['redis'] = {
                'status': 'degraded',
                'message': 'Using in-memory fallback',
            }
        else:
            dependencies['redis'] = {'status': 'unavailable'}
            status = 'degraded'
    except Exception as e:
        dependencies['redis'] = {'status': 'error', 'message': str(e)}
        status = 'degraded'

    # Check PostgreSQL
    try:
        from app.storage import get_postgres_db

        db = get_postgres_db()
        if db:
            dependencies['postgres'] = {'status': 'ok'}
        else:
            dependencies['postgres'] = {'status': 'unavailable'}
            status = 'degraded'
    except Exception as e:
        dependencies['postgres'] = {'status': 'error', 'message': str(e)}
        status = 'degraded'

    return {
        'status': status,
        'module_id': settings.MODULE_ID,
        'version': settings.MODULE_VERSION,
        'dependencies': dependencies,
    }


@system_router.get('/metrics')
async def metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response

    from app.metrics import get_metrics, get_metrics_content_type

    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail='Metrics disabled')

    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )


@system_router.get('/profiling')
async def profiling_stats():
    """Get async profiling statistics.

    Returns timing statistics for profiled operations.
    Useful for identifying performance bottlenecks.
    """
    from app.profiling import get_profiler

    profiler = get_profiler()
    stats = profiler.get_all_stats()

    return {
        'operations': stats,
        'total_operations': len(stats),
    }


@system_router.get('/')
async def root():
    """Root endpoint - API information."""
    return {
        'name': settings.MODULE_DESCRIPTION,
        'version': settings.MODULE_VERSION,
        'docs': '/docs',
        'health': '/health',
        'agentbench': {
            'metadata': '/metadata',
            'run': '/run',
            'run_debug': '/run_debug',
        },
        'agentos': {
            'config': '/config',
            'agents': '/agents',
            'sessions': '/sessions',
        },
    }


custom_app.include_router(system_router)


# =============================================================================
# AgentOS Setup
# =============================================================================

# Create the agent for AgentOS
agent = get_configured_agent()

# Create AgentOS instance (without built-in authorization - we add it manually)
agent_os = AgentOS(
    id=settings.MODULE_ID,
    name=settings.MODULE_DESCRIPTION,
    version=settings.MODULE_VERSION,
    agents=[agent],
    db=get_postgres_db(),
    authorization=False,  # We add JWT middleware manually for excluded paths
    cors_allowed_origins=settings.CORS_ORIGINS,
    base_app=custom_app,
    # Preserve our custom routes (AgentBench, auth, prompt, health)
    on_route_conflict='preserve_base_app',
)

# Get the final FastAPI application
app = agent_os.get_app()

# Add Request ID middleware (first, so it's available to all other middleware)
app.add_middleware(RequestIDMiddleware)

# Add Metrics middleware
if settings.METRICS_ENABLED:
    from app.metrics import MetricsMiddleware

    app.add_middleware(MetricsMiddleware)
    logger.info('Prometheus metrics enabled')

# Add Rate Limiting middleware (using Redis when available)
if settings.RATE_LIMIT_ENABLED:
    from app.rate_limiter import \
        RateLimitMiddleware as RedisRateLimitMiddleware

    logger.info(
        f'Rate limiting enabled: {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} '
        'requests/minute (Redis-backed)'
    )
    app.add_middleware(
        RedisRateLimitMiddleware,
        requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
    )

# Add JWT middleware with excluded paths
if settings.AUTH_ENABLED and settings.JWT_SECRET:
    logger.info(f'Adding JWT middleware (algorithm: {settings.JWT_ALGORITHM})')
    app.add_middleware(
        JWTMiddleware,
        verification_keys=[settings.JWT_SECRET],
        algorithm=settings.JWT_ALGORITHM,
        excluded_route_paths=[
            '/',
            '/health',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json',
            '/auth/login',
            '/auth/token',
            '/prompt/webhook',
        ],
    )

# Add Security Headers middleware
from app.security import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)
logger.info('Security headers middleware enabled')

# Add CORS middleware with explicit configuration
from starlette.middleware.cors import CORSMiddleware

cors_origins = settings.CORS_ORIGINS + ['https://agentbench.asanioficial.com']
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['Content-Type', 'Authorization'],
)
logger.info(f'CORS enabled for origins: {cors_origins}')

# Setup OpenTelemetry tracing
if settings.OTEL_ENABLED:
    from app.tracing import setup_tracing

    setup_tracing(app)
    logger.info('OpenTelemetry tracing enabled')


# =============================================================================
# Development Server
# =============================================================================

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'app.main:app',
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
