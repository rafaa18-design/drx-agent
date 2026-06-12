"""Tools de agenda Google Calendar para DRX."""

import logging

import httpx

from app.runtime import RetryAgentRun, RunContext, tool

logger = logging.getLogger(__name__)

_API = "http://localhost:8000"


@tool
async def check_availability(run_context: RunContext, date: str, duration_minutes: int = 60) -> str:
    """Verifica horários disponíveis na agenda do advogado para uma data.

    Use antes de propor horários ao cliente. Requer qualify_lead chamado antes.

    Args:
        date: Data no formato YYYY-MM-DD.
        duration_minutes: Duração da consulta em minutos (padrão: 60).

    Returns:
        Lista de horários disponíveis.
    """
    from app.services.calendar_service import CalendarService

    # Gate: o lead PRECISA estar qualificado antes de oferecer horários.
    # Garante que o score seja calculado e salvo no CRM em toda conversa.
    if not run_context.session_state.get("qualification"):
        raise RetryAgentRun(
            "Antes de oferecer horários, chame qualify_lead com os sinais coletados na conversa. "
            "Mapeie o que o lead disse para os sinais: seguidores (ex: 90 mil → followers_10k_to_100k), "
            "uso profissional/fonte de renda → professional_use, marketing digital → digital_marketing, "
            "restrição/banimento → temporary_restriction ou permanent_ban. "
            "Depois chame check_availability novamente."
        )

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

        # Guarda os slots válidos na sessão — book_appointment valida contra essa lista
        # (o modelo às vezes troca mês/dia ao copiar o slot_iso de cabeça).
        run_context.session_state["available_slots"] = [f"{date}T{s}:00" for s in slots]

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
    from zoneinfo import ZoneInfo as _ZI
    try:
        _parsed = _dt.fromisoformat(slot_datetime)
        # O slot vem como horário de Brasília — anexa o fuso para o Postgres
        # não tratar como UTC (senão o dashboard mostra 3h a menos).
        if _parsed.tzinfo is None:
            _parsed = _parsed.replace(tzinfo=_ZI("America/Sao_Paulo"))
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

    # Valida que o slot é exatamente um dos retornados por check_availability —
    # o modelo às vezes troca o mês/dia ao copiar o slot_iso de cabeça.
    available_slots = run_context.session_state.get("available_slots")
    if available_slots and slot_datetime not in available_slots:
        raise RetryAgentRun(
            f"ERRO: slot_datetime '{slot_datetime}' não é um dos horários retornados por check_availability. "
            f"Use EXATAMENTE um destes valores: {', '.join(available_slots)}"
        )

    from zoneinfo import ZoneInfo

    # Guarda contra chamada dupla — retorna o agendamento já criado
    existing = run_context.session_state.get("last_appointment")
    if existing and existing.get("scheduled_at"):
        try:
            dt = _dt.fromisoformat(str(existing["scheduled_at"])).replace(
                tzinfo=ZoneInfo("America/Sao_Paulo")
            )
            formatted = dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            formatted = str(existing.get("scheduled_at", ""))
        meet_line = f"\nLink Meet: {existing['google_meet_link']}" if existing.get("google_meet_link") else ""
        return f"Agendamento já registrado.\nData: {formatted}{meet_line}"

    # Resolve o telefone da sessão para localizar/criar o lead
    phone = (
        run_context.session_state.get("phone")
        or getattr(run_context, "conversation_id", None)
        or getattr(run_context, "session_id", None)
    )
    db_lead_id = run_context.session_state.get("db_lead_id")
    duration = int(os.environ.get("APPOINTMENT_DURATION_MINUTES", "60"))

    # Grava DIRETO no banco — sem depender de HTTP interno (mais robusto no Render)
    from app.db.session import AsyncSessionLocal
    from app.db.models import Appointment as ApptModel, Lead as LeadModel
    from sqlalchemy import select as sa_select

    try:
        async with AsyncSessionLocal() as db:
            # Localiza o lead por id, depois por telefone; cria se não existir
            lead = None
            if db_lead_id:
                lead = await db.get(LeadModel, db_lead_id)
            if lead is None and phone:
                res = await db.execute(
                    sa_select(LeadModel).where(LeadModel.phone == str(phone))
                )
                lead = res.scalar_one_or_none()
            if lead is None and phone:
                lead = LeadModel(
                    phone=str(phone),
                    name=run_context.session_state.get("client_name") or client_name,
                    source=run_context.session_state.get("lead_source", "unknown"),
                )
                db.add(lead)
                await db.flush()
            if lead is None:
                raise RetryAgentRun(
                    "Não consegui localizar o lead. Chame get_lead_context com o telefone antes de agendar."
                )

            run_context.session_state["db_lead_id"] = lead.id

            appt = ApptModel(
                lead_id=lead.id,
                scheduled_at=_parsed,
                duration_minutes=duration,
                appointment_type=appointment_type,
                notes=f"Cliente: {client_name} | Canal: {channel}",
                status="scheduled",
            )

            # Cria evento no Google Calendar (mock em dev) quando for Meet
            meet_link = None
            if channel != "whatsapp":
                try:
                    from app.services.calendar_service import CalendarService
                    service = CalendarService()
                    result = await service.create_appointment(
                        lead_id=lead.id,
                        slot_datetime=_parsed.isoformat(),
                        client_name=lead.name or lead.phone,
                        appointment_type=appointment_type,
                    )
                    appt.google_event_id = result.get("event_id")
                    appt.google_meet_link = result.get("meet_link")
                    meet_link = result.get("meet_link")
                except Exception as e:
                    logger.warning("Falha ao criar evento no Calendar: %s", e)

            db.add(appt)
            lead.commercial_status = "proposal"
            await db.commit()
            await db.refresh(appt)

            appt_id = appt.id

        run_context.session_state["last_appointment"] = {
            "id": appt_id,
            "scheduled_at": _parsed.isoformat(),
            "google_meet_link": meet_link,
        }

        formatted = _parsed.replace(tzinfo=ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y às %H:%M")
        meet_line = f"\nLink Meet: {meet_link}" if meet_link else ""
        return (
            f"AGENDAMENTO SALVO COM SUCESSO. Responda ao lead confirmando.\n"
            f"Data: {formatted}\n"
            f"Duração: {duration} minutos"
            f"{meet_line}"
        )

    except RetryAgentRun:
        raise
    except Exception as e:
        logger.error("book_appointment falhou: %s", e)
        raise RetryAgentRun(f"Erro ao criar agendamento: {e}")
