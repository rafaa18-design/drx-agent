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
        from datetime import datetime
        dt = datetime.strptime(date, "%Y-%m-%d")
        data_formatada = dt.strftime("%d/%m/%Y")
        dia_semana = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado","Domingo"][dt.weekday()]

        service = CalendarService()
        slots = await service.get_available_slots(date, duration_minutes)
        if not slots:
            return f"Nenhum horário disponível em {dia_semana}, {data_formatada}. Sugira outra data."

        from datetime import datetime as _now_dt
        ano_atual = _now_dt.now().year

        linhas = [f"ANO ATUAL: {ano_atual} — use este ano em todos os agendamentos."]
        linhas.append(f"DATA: {dia_semana}, {data_formatada} ({date})")
        linhas.append("INSTRUÇÃO: copie o campo slot_iso abaixo EXATAMENTE em book_appointment. NÃO construa o valor manualmente.")
        for s in slots:
            iso = f"{date}T{s}:00"
            linhas.append(f"  - {s} → slot_iso={iso}")
        return "\n".join(linhas)
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
        slot_datetime: Data e hora ISO exata retornada por check_availability (ex: 2026-05-23T09:00:00). NUNCA construa esse valor manualmente — copie o slot_iso do resultado de check_availability.
        client_name: Nome completo do cliente.
        channel: Canal da reunião — "meet" para Google Meet, "whatsapp" para WhatsApp.
        appointment_type: Tipo de consulta (initial_consultation, follow_up).

    Returns:
        Confirmação com data/hora e canal.
    """
    import os
    from datetime import datetime as _dt

    # Rejeita ano errado — o modelo às vezes constrói datas com ano defasado
    try:
        _parsed = _dt.fromisoformat(slot_datetime)
        _current_year = _dt.now().year
        if _parsed.year != _current_year:
            raise RetryAgentRun(
                f"ERRO: slot_datetime tem o ano {_parsed.year}, mas o ano atual é {_current_year}. "
                f"Copie o valor slot_iso EXATAMENTE como retornado por check_availability — "
                f"não construa o valor manualmente. Exemplo correto: {_current_year}-05-27T10:00:00"
            )
    except ValueError:
        raise RetryAgentRun(
            f"slot_datetime inválido: '{slot_datetime}'. "
            f"Use o formato ISO retornado por check_availability: YYYY-MM-DDTHH:MM:SS"
        )

    db_lead_id = run_context.session_state.get("db_lead_id")
    if not db_lead_id:
        # Recuperação automática: busca ou cria o lead pelo telefone da sessão,
        # para o agendamento nunca quebrar mesmo se get_lead_context não rodou.
        phone = (
            run_context.session_state.get("phone")
            or getattr(run_context, "conversation_id", None)
            or getattr(run_context, "session_id", None)
        )
        if phone:
            try:
                async with httpx.AsyncClient(timeout=10.0) as _http:
                    _r = await _http.get(f"{_API}/api/leads", params={"search": phone})
                    _items = _r.json().get("items", []) if _r.status_code == 200 else []
                    if _items:
                        db_lead_id = _items[0]["id"]
                    else:
                        _c = await _http.post(f"{_API}/api/leads", json={
                            "phone": str(phone),
                            "name": run_context.session_state.get("client_name") or client_name,
                            "source": run_context.session_state.get("lead_source", "unknown"),
                        })
                        if _c.status_code in (200, 201):
                            db_lead_id = _c.json()["id"]
                if db_lead_id:
                    run_context.session_state["db_lead_id"] = db_lead_id
            except Exception as e:
                logger.warning("Falha na recuperação automática do lead: %s", e)

    if not db_lead_id:
        raise RetryAgentRun(
            "Não consegui localizar o lead. Chame get_lead_context com o telefone antes de agendar."
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
