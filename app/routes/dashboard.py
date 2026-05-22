"""Endpoints de métricas para o dashboard DRX."""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/kpis")
async def get_kpis(
    date_from: str | None = Query(default=None, description="YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD"),
) -> dict:
    """KPIs principais: total leads, agendamentos, conversão."""
    # TODO: queries agregadas no banco
    return {
        "leads_total": 0,
        "leads_this_month": 0,
        "appointments_scheduled": 0,
        "appointments_completed": 0,
        "escalation_rate": 0.0,
        "avg_response_seconds": 0.0,
        "conversion_rate": 0.0,
    }


@router.get("/funnel")
async def get_funnel(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> dict:
    """Dados do funil de conversão: new → won."""
    # TODO: count por commercial_status no banco
    stages = ["new", "contacted", "qualified", "proposal", "won", "lost"]
    return {"stages": [{"stage": s, "count": 0} for s in stages]}


@router.get("/agent-metrics")
async def get_agent_metrics(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> dict:
    """Performance do agente IA: mensagens, escalações, tempo de resposta."""
    # TODO: agregar de messages + conversations no banco
    return {
        "messages_handled_by_ai": 0,
        "messages_escalated": 0,
        "escalation_rate": 0.0,
        "avg_response_seconds": 0.0,
        "top_escalation_reasons": [],
    }


@router.get("/appointments")
async def get_appointment_metrics(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> dict:
    """Métricas de agendamentos: realizados, no-show, cancelamentos."""
    # TODO: agregar de appointments no banco
    return {
        "scheduled": 0,
        "confirmed": 0,
        "completed": 0,
        "no_show": 0,
        "cancelled": 0,
        "no_show_rate": 0.0,
        "avg_lead_to_appointment_hours": 0.0,
    }
