"""Endpoints CRM — Dashboard KPIs e métricas."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment, Conversation, Lead
from app.db.session import get_db

router = APIRouter(prefix="/api/dashboard", tags=["CRM · Dashboard"])


@router.get("/kpis")
async def get_kpis(db: AsyncSession = Depends(get_db)):
    """KPIs principais do dashboard DRX."""
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_30 = now - timedelta(days=30)

    # Leads este mês
    leads_month = (await db.execute(
        select(func.count()).where(Lead.created_at >= start_of_month)
    )).scalar_one()

    # Agendamentos este mês
    appts_month = (await db.execute(
        select(func.count()).where(
            Appointment.created_at >= start_of_month,
            Appointment.status != "cancelled",
        )
    )).scalar_one()

    # Taxa de conversão — leads que viraram "won" nos últimos 30 dias
    total_leads = (await db.execute(
        select(func.count()).where(Lead.created_at >= last_30)
    )).scalar_one() or 1

    won_leads = (await db.execute(
        select(func.count()).where(
            Lead.commercial_status == "won",
            Lead.updated_at >= last_30,
        )
    )).scalar_one()

    conversion_rate = won_leads / total_leads

    # Taxa de escalação — conversas que foram para humano
    total_convs = (await db.execute(
        select(func.count()).where(Conversation.started_at >= last_30)
    )).scalar_one() or 1

    escalated = (await db.execute(
        select(func.count()).where(
            Conversation.status == "human_required",
            Conversation.started_at >= last_30,
        )
    )).scalar_one()

    escalation_rate = escalated / total_convs

    # Leads com IA ativa vs desligada
    ai_active = (await db.execute(
        select(func.count()).where(Lead.ai_active == True)  # noqa: E712
    )).scalar_one()

    ai_inactive = (await db.execute(
        select(func.count()).where(Lead.ai_active == False)  # noqa: E712
    )).scalar_one()

    return {
        "leads_this_month": leads_month,
        "appointments_scheduled": appts_month,
        "conversion_rate": round(conversion_rate, 4),
        "escalation_rate": round(escalation_rate, 4),
        "ai_active_leads": ai_active,
        "ai_inactive_leads": ai_inactive,
        "total_leads": (await db.execute(select(func.count(Lead.id)))).scalar_one(),
    }


@router.get("/funnel")
async def get_funnel(db: AsyncSession = Depends(get_db)):
    """Funil de conversão por estágio do pipeline."""
    stages_order = ["new", "contacted", "qualified", "proposal", "won", "lost"]

    result = await db.execute(
        select(Lead.commercial_status, func.count().label("count"))
        .group_by(Lead.commercial_status)
    )
    counts = {row[0]: row[1] for row in result.all()}

    return {
        "stages": [
            {"stage": s, "count": counts.get(s, 0)}
            for s in stages_order
        ]
    }


@router.get("/agent-metrics")
async def get_agent_metrics(db: AsyncSession = Depends(get_db)):
    """Métricas do agente Tiago."""
    total = (await db.execute(select(func.count(Lead.id)))).scalar_one() or 1

    auto_meeting = (await db.execute(
        select(func.count()).where(Lead.qualification_level == "auto_meeting")
    )).scalar_one()

    hot = (await db.execute(
        select(func.count()).where(Lead.qualification_level == "hot")
    )).scalar_one()

    warm = (await db.execute(
        select(func.count()).where(Lead.qualification_level == "warm")
    )).scalar_one()

    cold = (await db.execute(
        select(func.count()).where(Lead.qualification_level == "cold")
    )).scalar_one()

    disqualified = (await db.execute(
        select(func.count()).where(Lead.qualification_level == "disqualified")
    )).scalar_one()

    avg_score = (await db.execute(
        select(func.avg(Lead.qualification_score))
    )).scalar_one() or 0

    return {
        "total_qualified": total,
        "auto_meeting": auto_meeting,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "disqualified": disqualified,
        "average_score": round(float(avg_score), 1),
    }


@router.get("/appointments")
async def get_appointment_metrics(db: AsyncSession = Depends(get_db)):
    """Métricas de agendamentos."""
    now = datetime.now(timezone.utc)
    next_7 = now + timedelta(days=7)

    upcoming = (await db.execute(
        select(func.count()).where(
            Appointment.scheduled_at >= now,
            Appointment.scheduled_at <= next_7,
            Appointment.status == "scheduled",
        )
    )).scalar_one()

    completed = (await db.execute(
        select(func.count()).where(Appointment.status == "completed")
    )).scalar_one()

    cancelled = (await db.execute(
        select(func.count()).where(Appointment.status == "cancelled")
    )).scalar_one()

    no_show = (await db.execute(
        select(func.count()).where(Appointment.status == "no_show")
    )).scalar_one()

    return {
        "upcoming_7_days": upcoming,
        "completed": completed,
        "cancelled": cancelled,
        "no_show": no_show,
    }
