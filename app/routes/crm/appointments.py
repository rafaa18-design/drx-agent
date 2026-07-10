"""Endpoints CRM — Agendamentos."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment, Lawyer, Lead
from app.db.session import get_db
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/api/appointments", tags=["CRM · Agendamentos"])


# ── Schemas ────────────────────────────────────────────────────────────────

class AppointmentOut(BaseModel):
    id: str
    lead_id: str
    lawyer_id: str | None
    google_event_id: str | None
    google_meet_link: str | None
    scheduled_at: datetime
    duration_minutes: int
    status: str
    appointment_type: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentCreate(BaseModel):
    lead_id: str
    scheduled_at: datetime
    duration_minutes: int = 60
    appointment_type: str = "initial_consultation"
    channel: str = "meet"
    lawyer_id: str | None = None
    client_email: str | None = None
    notes: str | None = None
    google_event_id: str | None = None
    google_meet_link: str | None = None


class AppointmentUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    scheduled_at: datetime | None = None


# ── Helpers ────────────────────────────────────────────────────────────────

def appt_to_dict(a: Appointment, lead: Lead | None = None) -> dict:
    return {
        "id": a.id,
        "lead_id": a.lead_id,
        "lead_name": lead.name if lead else None,
        "lead_phone": lead.phone if lead else None,
        "lawyer_id": a.lawyer_id,
        "google_event_id": a.google_event_id,
        "google_meet_link": a.google_meet_link,
        "scheduled_at": a.scheduled_at,
        "duration_minutes": a.duration_minutes,
        "status": a.status,
        "appointment_type": a.appointment_type,
        "notes": a.notes,
        "created_at": a.created_at,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
async def list_appointments(
    status: str | None = Query(None),
    lead_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Lista agendamentos com filtros, incluindo nome e telefone do lead."""
    from sqlalchemy import case
    from sqlalchemy.orm import joinedload

    # Ordem de agenda: próxima reunião a acontecer primeiro (futuras em ordem
    # crescente), depois as passadas (mais recente que passou primeiro).
    now = datetime.now(timezone.utc)
    is_future = Appointment.scheduled_at >= now
    q = (
        select(Appointment)
        .options(joinedload(Appointment.lead))
        .order_by(
            case((is_future, 0), else_=1),
            case((is_future, Appointment.scheduled_at)).asc(),
            case((~is_future, Appointment.scheduled_at)).desc(),
        )
    )

    if status:
        q = q.where(Appointment.status == status)
    if lead_id:
        q = q.where(Appointment.lead_id == lead_id)

    count_q = select(func.count(Appointment.id))
    if status:
        count_q = count_q.where(Appointment.status == status)
    if lead_id:
        count_q = count_q.where(Appointment.lead_id == lead_id)
    total = (await db.execute(count_q)).scalar_one()

    result = await db.execute(q.limit(limit).offset(offset))
    appts = result.scalars().unique().all()

    return {"items": [appt_to_dict(a, a.lead) for a in appts], "total": total}


async def _resolve_lawyer(db: AsyncSession, lawyer_id: str | None) -> Lawyer | None:
    if lawyer_id:
        return await db.get(Lawyer, lawyer_id)
    result = await db.execute(select(Lawyer).where(Lawyer.is_default.is_(True)))
    return result.scalar_one_or_none()


@router.get("/calendar/availability")
async def get_availability(
    date: str = Query(..., description="Data no formato YYYY-MM-DD"),
    duration: int = Query(60),
    lawyer_id: str | None = Query(None, description="Se omitido, usa o advogado padrão"),
    db: AsyncSession = Depends(get_db),
):
    """Consulta horários disponíveis no Google Calendar do advogado (ou mock em dev)."""
    try:
        lawyer = await _resolve_lawyer(db, lawyer_id)
        service = CalendarService(lawyer=lawyer)
        slots = await service.get_available_slots(date, duration)
        return {"available_slots": slots, "date": date, "duration_minutes": duration}
    except Exception as e:
        return {"available_slots": [], "date": date, "error": str(e)}


@router.get("/{appt_id}")
async def get_appointment(appt_id: str, db: AsyncSession = Depends(get_db)):
    appt = await db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    return appt_to_dict(appt)


@router.post("", status_code=201)
async def create_appointment(body: AppointmentCreate, db: AsyncSession = Depends(get_db)):
    """Cria agendamento e tenta criar evento no Google Calendar do advogado."""
    lead = await db.get(Lead, body.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    lawyer = await _resolve_lawyer(db, body.lawyer_id)

    appt = Appointment(
        lead_id=body.lead_id,
        scheduled_at=body.scheduled_at,
        duration_minutes=body.duration_minutes,
        appointment_type=body.appointment_type,
        lawyer_id=lawyer.id if lawyer else None,
        notes=body.notes,
        status="scheduled",
    )

    # Sempre tenta criar o evento no calendário do advogado (nos dois canais) —
    # sem advogado resolvido, não há de quem calendário usar, então pula.
    calendar_event_created = False
    if lawyer:
        try:
            service = CalendarService(lawyer=lawyer)
            result = await service.create_appointment(
                lead_id=body.lead_id,
                slot_datetime=body.scheduled_at.isoformat(),
                client_name=lead.name or lead.phone,
                channel=body.channel,
                client_email=(body.client_email or "") if body.channel == "meet" else "",
                appointment_type=body.appointment_type or "initial_consultation",
            )
            appt.google_event_id = result.get("event_id")
            appt.google_meet_link = result.get("meet_link") or None
            calendar_event_created = True
        except Exception:
            pass  # Falha silenciosa — agendamento salvo sem Calendar

    db.add(appt)
    await db.flush()

    # Atualiza status do lead para "proposal"
    lead.commercial_status = "proposal"
    lead.updated_at = datetime.now(timezone.utc)

    return {**appt_to_dict(appt), "calendar_event_created": calendar_event_created}


@router.patch("/{appt_id}")
async def update_appointment(
    appt_id: str,
    body: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    appt = await db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(appt, field, value)

    return appt_to_dict(appt)
