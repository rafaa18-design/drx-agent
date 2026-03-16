"""System routes: /health, /metrics, /profiling, /."""

from fastapi import APIRouter, HTTPException

from app.config import settings

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
    """Get async profiling statistics."""
    from app.profiling import get_profiler

    profiler = get_profiler()
    stats = profiler.get_all_stats()

    return {
        'operations': stats,
        'total_operations': len(stats),
    }


@system_router.post('/reset/{conversation_id}')
async def reset_session(conversation_id: str):
    """Reset session state, message history, and memory for a conversation."""
    from app.memory import clear_memory
    from app.storage import clear_message_history, delete_session_state

    await delete_session_state(conversation_id)
    await clear_message_history(conversation_id)
    await clear_memory(conversation_id)

    return {'status': 'ok', 'conversation_id': conversation_id, 'message': 'Session reset'}


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
    }
