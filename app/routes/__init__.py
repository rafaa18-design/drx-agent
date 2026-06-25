"""Route sub-package: AgentBench, auth, prompts, system and DRX CRM endpoints."""

from app.routes.agentbench import agentbench_router, router_debug as debug_router
from app.routes.appointments import router as appointments_router
from app.routes.auth import auth_router
from app.routes.conversations import router as conversations_router
from app.routes.dashboard import router as dashboard_router
from app.routes.leads import router as leads_router
from app.routes.prompts import prompt_router
from app.routes.system import system_router
from app.routes.webhooks import router as webhooks_router

__all__ = [
    "agentbench_router",
    "debug_router",
    "auth_router",
    "prompt_router",
    "system_router",
    "webhooks_router",
    "leads_router",
    "appointments_router",
    "conversations_router",
    "dashboard_router",
]
