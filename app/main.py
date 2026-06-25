"""Asani AI Agent Template - LiteLLM Agent with AgentBench Standard.

This module sets up a FastAPI application with:
- AgentBench Standard endpoints (/metadata, /run, /run_debug)
- JWT authentication via custom middleware
- Custom routes for prompt management
- Redis for caching and session state
- Langfuse for observability
- Rate limiting and request tracing
- LLM-driven memory consolidation
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import JWTAuthMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware
from app.observability import get_langfuse, get_logger, setup_langfuse_env, setup_logging, setup_tracing, shutdown_langfuse, shutdown_tracing
from app.routes import agentbench_router, auth_router, debug_router, prompt_router, system_router
from app.routes.crm import crm_router
from app.storage import close_redis, get_redis

# Setup logging early (must be before other app imports that use loggers)
setup_logging()

logger = get_logger(__name__)


# =============================================================================
# Application Lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler with graceful shutdown."""
    from app.memory import shutdown_consolidation
    from app.prompt_manager import get_prompt_manager

    # Startup
    setup_langfuse_env()
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

    # Wait for consolidation tasks
    await shutdown_consolidation(timeout=5.0)

    # Cleanup resources
    shutdown_tracing()
    await close_redis()
    shutdown_langfuse()
    logger.info('Application shutdown complete')


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(
    title=settings.MODULE_DESCRIPTION,
    version=settings.MODULE_VERSION,
    lifespan=lifespan,
)

# --- Routers ---
app.include_router(agentbench_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.include_router(prompt_router)
app.include_router(system_router)
app.include_router(crm_router)

# --- WebSocket (registrado direto no app — não passa por routers aninhados) ---
_ws_clients: list[WebSocket] = []


@app.websocket('/ws/conversations')
async def ws_conversations(websocket: WebSocket) -> None:
    """WebSocket para atualizações em tempo real do CRM."""
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # mantém conexão viva
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)


async def broadcast_ws(payload: dict) -> None:
    """Broadcast para todos os clientes WebSocket conectados."""
    import json
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)

# --- Middlewares ---
# (Order matters: first added = outermost = runs first on request)

# Request ID (outermost, so it's available to all other middleware)
app.add_middleware(RequestIDMiddleware)

# Metrics
if settings.METRICS_ENABLED:
    from app.metrics import MetricsMiddleware

    app.add_middleware(MetricsMiddleware)
    logger.info('Prometheus metrics enabled')

# Rate Limiting (Redis-backed)
if settings.RATE_LIMIT_ENABLED:
    from app.rate_limiter import RateLimitMiddleware as RedisRateLimitMiddleware

    logger.info(
        f'Rate limiting enabled: {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} '
        'requests/minute (Redis-backed)'
    )
    app.add_middleware(
        RedisRateLimitMiddleware,
        requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
    )

# JWT Authentication
if settings.AUTH_ENABLED and settings.JWT_SECRET:
    logger.info(f'Adding JWT middleware (algorithm: {settings.JWT_ALGORITHM})')
    app.add_middleware(JWTAuthMiddleware)

# Security Headers
app.add_middleware(SecurityHeadersMiddleware)
logger.info('Security headers middleware enabled')

# CORS
cors_origins = settings.CORS_ORIGINS + ['https://agentbench.asanioficial.com']

# Em desenvolvimento, adiciona localhost em todas as portas comuns
if settings.OTEL_ENVIRONMENT != 'production':
    cors_origins += [
        'http://localhost:3000',
        'http://localhost:3001',
        'http://localhost:3002',
        'http://localhost:3003',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:3001',
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Content-Type', 'Authorization', 'X-Request-ID'],
)
logger.info(f'CORS enabled for origins: {cors_origins}')


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
