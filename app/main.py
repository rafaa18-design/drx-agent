"""Asani AI Agent Template - AgentBench Standard.

FastAPI application exposing the three required AgentBench endpoints:
- GET /metadata - Module capabilities and configuration
- POST /run - Production execution
- POST /run_debug - Debug execution with full trajectory

Integrates with:
- Langfuse for observability and prompt management
- Redis for session state and cache
- PostgreSQL for persistent storage
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.agent import run_agent, run_agent_debug
from app.config import settings
from app.langfuse_client import get_langfuse
from app.langfuse_client import shutdown as langfuse_shutdown
from app.models import (
    Capabilities,
    InputTypes,
    MetadataResponse,
    Pipeline,
    PipelineStage,
    RunDebugResponse,
    RunRequest,
    RunResponse,
    ToolExposed,
)
from app.storage import close_redis, get_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    get_langfuse()
    try:
        await get_redis()
        logger.info('Storage backends initialized')
    except Exception as e:
        logger.warning(f'Redis not available: {e}')

    yield

    # Shutdown
    await close_redis()
    langfuse_shutdown()
    logger.info('Application shutdown complete')


app = FastAPI(
    title=settings.MODULE_DESCRIPTION,
    version=settings.MODULE_VERSION,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)


# =============================================================================
# AgentBench Standard Endpoints
# =============================================================================


@app.get('/metadata', response_model=MetadataResponse)
async def get_metadata() -> MetadataResponse:
    """Return module metadata.

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
        tools_exposed=[
            ToolExposed(
                name='get_current_time',
                description='Get the current date and time in ISO format',
            ),
            ToolExposed(
                name='calculate',
                description='Evaluate a mathematical expression',
                parameters_schema={'expression': 'string'},
            ),
        ],
        input_types=InputTypes(
            supported_types=['text', 'image', 'audio', 'video', 'document'],
            allowed_formats={
                'image': ['jpeg', 'jpg', 'png', 'webp'],
                'audio': ['mp3', 'wav', 'ogg'],
                'video': ['mp4', 'webm'],
                'document': ['pdf', 'txt', 'md', 'json', 'docx', 'csv'],
            },
        ),
        models_supported=[
            'claude-sonnet-4-20250514',
            'claude-3-5-sonnet-20241022',
            'gpt-4o',
            'gpt-4-turbo',
        ],
    )


@app.post('/run', response_model=RunResponse)
async def run(request: RunRequest) -> RunResponse:
    """Execute the agent in production mode.

    Processes the input and returns the final response with basic metrics.
    The module manages conversation history internally using conversation_id.
    """
    return await run_agent(
        conversation_id=request.conversation_id,
        items=request.input,
        model=request.model,
    )


@app.post('/run_debug', response_model=RunDebugResponse)
async def run_debug(request: RunRequest) -> RunDebugResponse:
    """Execute the agent in debug mode.

    Same as /run but includes full trajectory for observability.
    Useful for testing and benchmarking.
    """
    return await run_agent_debug(
        conversation_id=request.conversation_id,
        items=request.input,
        model=request.model,
    )


# =============================================================================
# Health Check
# =============================================================================


@app.get('/health')
async def health():
    """Health check endpoint."""
    return {'status': 'ok', 'module_id': settings.MODULE_ID}


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
