"""Endpoints de agendamentos — CRM DRX."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

AppointmentStatus = Literal["scheduled", "confirmed", "cancelled", "completed", "no_show"]


class AppointmentUpdate(BaseModel):
    status: AppointmentStatus | None = None
    notes: str | None = None


@router.get("")
async def list_appointments(
    status: AppointmentStatus | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    lead_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Lista agendamentos com filtros."""
    # TODO: query no banco
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.patch("/{appointment_id}")
async def update_appointment(appointment_id: uuid.UUID, body: AppointmentUpdate) -> dict:
    """Atualiza status ou notas de um agendamento."""
    # TODO: atualizar no banco
    return {"id": str(appointment_id), **body.model_dump(exclude_none=True)}


@router.get("/calendar/availability")
async def get_availability(
    date: str = Query(..., description="Data no formato YYYY-MM-DD"),
    duration: int = Query(default=60, description="Duração em minutos"),
) -> dict:
    """Consulta horários disponíveis no Google Calendar."""
    from app.services.calendar_service import CalendarService

    service = CalendarService()
    slots = await service.get_available_slots(date, duration)
    return {"date": date, "duration_minutes": duration, "available_slots": slots}
