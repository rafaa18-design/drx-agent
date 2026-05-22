"""CRM routes — Leads, Appointments, Conversations, Dashboard."""

from fastapi import APIRouter

from app.routes.crm.leads import router as leads_router
from app.routes.crm.appointments import router as appointments_router
from app.routes.crm.conversations import router as conversations_router
from app.routes.crm.dashboard import router as dashboard_router

crm_router = APIRouter()
crm_router.include_router(leads_router)
crm_router.include_router(appointments_router)
crm_router.include_router(conversations_router)
crm_router.include_router(dashboard_router)

__all__ = ["crm_router"]
