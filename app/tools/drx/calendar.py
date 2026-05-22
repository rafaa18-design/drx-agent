"""Tools de agenda Google Calendar para DRX."""

import logging

import httpx

from app.runtime import RetryAgentRun, RunContext, tool

logger = logging.getLogger(__name__)

_API = "http://localhost:8000"


@tool
async def check_availability(date: str, duration_minutes: int = 60) -> str:
    """Verifica horários disponíveis na agenda do advogado para uma data.

    Use antes de propor horários ao cliente.

    Args:
        date: Data no formato YYYY-MM-DD.
        duration_minutes: Duração da consulta em minutos (padrão: 60).

    Returns:
        Lista de horários disponíveis.
    """
    # TODO: integrar com CalendarService (Google Calendar API)
    from app.services.calendar_service import CalendarService

    try:
        service = CalendarService()
        slots = await service.get_available_slots(date, duration_minutes)
        if not slots:
            return f"Nenhum horário disponível em {date}. Sugira outra data."
        slots_str = "\n".join(f"- {s}" for s in slots)
        return f"Horários disponíveis em {date}:\n{slots_str}"
    except Exception as e:
        raise RetryAgentRun(f"Erro ao consultar agenda: {e}")


@tool
async def book_appointment(
    run_context: RunContext,
    slot_datetime: str,
    client_name: str,
    channel: str = "meet",
    appointment_type: str = "initial_consultation",
) -> str:
    """Cria evento no Google Calendar e registra o agendamento no CRM.

    Use após o cliente confirmar o horário desejado.
    O lead_id é obtido automaticamente da sessão.

    Args:
        slot_datetime: Data e hora no formato ISO (ex: 2025-03-15T10:00:00).
        client_name: Nome completo do cliente.
        channel: Canal da reunião — "meet" para Google Meet, "whatsapp" para WhatsApp.
        appointment_type: Tipo de consulta (initial_consultation, follow_up).

    Returns:
        Confirmação com data/hora e canal.
    """
    import os

    db_lead_id = run_context.session_state.get("db_lead_id")
    if not db_lead_id:
        raise RetryAgentRun(
            "Não encontrei o ID do lead na sessão. "
            "Chame get_lead_context antes de agendar."
        )

    # Guarda contra chamada dupla — retorna o agendamento já criado
    existing = run_context.session_state.get("last_appointment")
    if existing and existing.get("scheduled_at"):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:
            dt = datetime.fromisoformat(str(existing["scheduled_at"])).replace(
                tzinfo=ZoneInfo("America/Sao_Paulo")
            )
            formatted = dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            formatted = str(existing.get("scheduled_at", ""))
        meet_line = f"\nLink Meet: {existing['google_meet_link']}" if existing.get("google_meet_link") else ""
        return f"Agendamento já registrado.\nData: {formatted}{meet_line}"

    try:
        duration = int(os.environ.get("APPOINTMENT_DURATION_MINUTES", "60"))

        async with httpx.AsyncClient(timeout=10.0) as http:
            # Cria agendamento no CRM (que chama Calendar internamente)
            r = await http.post(f"{_API}/api/appointments", json={
                "lead_id": db_lead_id,
                "scheduled_at": slot_datetime,
                "duration_minutes": duration,
                "appointment_type": appointment_type,
                "channel": channel,
                "notes": f"Cliente: {client_name} | Canal: {channel}",
            })

            if r.status_code not in (200, 201):
                raise RetryAgentRun(
                    f"Erro ao registrar agendamento no CRM: {r.status_code} — {r.text[:200]}"
                )

            appt = r.json()

            # Atualiza status do lead para "proposal"
            await http.patch(f"{_API}/api/leads/{db_lead_id}", json={
                "commercial_status": "proposal"
            })

        run_context.session_state["last_appointment"] = appt

        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:
            dt = datetime.fromisoformat(slot_datetime).replace(
                tzinfo=ZoneInfo("America/Sao_Paulo")
            )
            formatted = dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            formatted = slot_datetime

        meet_line = f"\nLink Meet: {appt['google_meet_link']}" if appt.get("google_meet_link") else ""
        return (
            f"AGENDAMENTO SALVO COM SUCESSO. Responda ao lead confirmando.\n"
            f"Data: {formatted}\n"
            f"Duração: {duration} minutos"
            f"{meet_line}"
        )

    except RetryAgentRun:
        raise
    except Exception as e:
        raise RetryAgentRun(f"Erro ao criar agendamento: {e}")
