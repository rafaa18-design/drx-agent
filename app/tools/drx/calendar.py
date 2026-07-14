"""Tools de agenda Google Calendar para DRX."""

import logging
import re

from app.runtime import RetryAgentRun, RunContext, tool

logger = logging.getLogger(__name__)


async def _get_default_lawyer(db):
    """Advogado usado pelo Tiago ao agendar via WhatsApp (ainda sem atribuição
    manual por lead — todo agendamento cai no advogado marcado como padrão)."""
    from sqlalchemy import select as sa_select
    from app.db.models import Lawyer as LawyerModel

    result = await db.execute(sa_select(LawyerModel).where(LawyerModel.is_default.is_(True)))
    return result.scalar_one_or_none()


@tool
def save_client_email(run_context: RunContext, email: str) -> str:
    """Salva o e-mail do cliente — necessário antes de confirmar reunião por Google Meet.

    Só chame quando o cliente escolher reunião por vídeo (Meet). Reunião só por
    WhatsApp não precisa de e-mail.

    Args:
        email: E-mail informado pelo cliente.

    Returns:
        Confirmação para prosseguir com book_appointment.
    """
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
        raise RetryAgentRun(f"'{email}' não parece um e-mail válido. Peça o e-mail novamente ao cliente.")
    run_context.session_state["client_email"] = email.strip()
    return f"E-mail {email.strip()} salvo. Pode prosseguir com book_appointment(channel='meet', ...)."


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

    # Gate: leads com menos de 10k seguidores não agendam reunião.
    if run_context.session_state.get("meeting_blocked"):
        raise RetryAgentRun(
            "BLOQUEIO: este lead tem menos de 10 mil seguidores. "
            "NÃO chame check_availability nem ofereça reunião. "
            "Siga a regra de lead com poucos seguidores do prompt."
        )

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

    from datetime import datetime
    from zoneinfo import ZoneInfo as _ZoneInfo

    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        hoje = datetime.now(_ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d")
        raise RetryAgentRun(
            f"O parâmetro date='{date}' está em formato inválido (use YYYY-MM-DD). "
            f"A data de hoje é {hoje}. Chame check_availability novamente com date='{hoje}' "
            f"(ou outra data válida no formato YYYY-MM-DD). NUNCA pergunte ao lead a data de hoje, "
            f"você já sabe."
        )

    try:
        data_formatada = dt.strftime("%d/%m/%Y")
        dia_semana = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado","Domingo"][dt.weekday()]

        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            lawyer = await _get_default_lawyer(db)

        service = CalendarService(lawyer=lawyer)
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
    channel: str,
    appointment_type: str = "initial_consultation",
) -> str:
    """Cria evento no Google Calendar e registra o agendamento no CRM.

    Use só depois que o cliente já confirmou um horário de check_availability —
    é o último passo do agendamento, não algo para antecipar no início da
    conversa. Nesse momento (e só nesse momento), pergunte se ele prefere
    vídeo (Google Meet) ou uma ligação só pelo WhatsApp, e defina channel de
    acordo com a resposta:
    - Vídeo → channel="meet" (precisa do e-mail dele antes — veja save_client_email).
    - Só WhatsApp → channel="whatsapp" (não precisa de e-mail, não pergunte).

    O lead_id é obtido automaticamente da sessão.

    Depois que esta tool retornar sucesso, é o ÚLTIMO passo do atendimento —
    responda IMEDIATAMENTE com a confirmação do agendamento (dia/hora/canal).
    Nunca pergunte mais detalhes do caso, nunca repita etapas anteriores
    (seguidores, dor, print, etc.) depois de um agendamento bem-sucedido,
    mesmo que pareça uma boa transição de conversa — isso já foi concluído.

    Args:
        slot_datetime: Data e hora ISO exata retornada por check_availability (ex: 2026-05-23T09:00:00). NUNCA construa esse valor manualmente — copie o slot_iso do resultado de check_availability.
        client_name: Nome completo do cliente.
        channel: Canal da reunião — "meet" para Google Meet (vídeo), "whatsapp" para ligação só por WhatsApp. Escolha com base no que o cliente respondeu nessa etapa final, nunca herde um valor sem perguntar.
        appointment_type: Tipo de consulta (initial_consultation, follow_up).

    Returns:
        Confirmação com data/hora e canal.
    """
    import os
    from datetime import datetime as _dt

    logger.info(
        "book_appointment chamado: slot=%s client_name=%s channel=%s phone_session=%s db_lead_id=%s",
        slot_datetime, client_name, channel,
        run_context.session_state.get("phone"),
        run_context.session_state.get("db_lead_id"),
    )

    if channel not in ("meet", "whatsapp"):
        raise RetryAgentRun(
            f"channel='{channel}' inválido. Use exatamente 'meet' (cliente prefere vídeo) "
            f"ou 'whatsapp' (cliente prefere ligação só por WhatsApp) — pergunte ao cliente "
            f"se ainda não sabe qual ele prefere."
        )

    # Reunião por vídeo precisa do e-mail do cliente ANTES de confirmar — é
    # esse e-mail que o Google usa para mandar o convite com o link do Meet.
    if channel == "meet" and not run_context.session_state.get("client_email"):
        raise RetryAgentRun(
            "Antes de confirmar reunião por Google Meet, pergunte o e-mail do cliente "
            "e chame save_client_email. Depois tente book_appointment novamente."
        )

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

            lawyer = await _get_default_lawyer(db)

            appt = ApptModel(
                lead_id=lead.id,
                lawyer_id=lawyer.id if lawyer else None,
                scheduled_at=_parsed,
                duration_minutes=duration,
                appointment_type=appointment_type,
                notes=f"Cliente: {client_name} | Canal: {channel}",
                status="scheduled",
            )

            # Sempre cria o evento no calendário do advogado (nos dois canais) —
            # só o link de Meet/e-mail ao cliente depende de channel=="meet".
            meet_link = None
            try:
                from app.services.calendar_service import CalendarService
                service = CalendarService(lawyer=lawyer)
                result = await service.create_appointment(
                    lead_id=lead.id,
                    slot_datetime=_parsed.isoformat(),
                    client_name=lead.name or lead.phone,
                    channel=channel,
                    client_email=run_context.session_state.get("client_email", "") if channel == "meet" else "",
                    appointment_type=appointment_type,
                )
                appt.google_event_id = result.get("event_id")
                appt.google_meet_link = result.get("meet_link") or None
                meet_link = result.get("meet_link")
            except Exception as e:
                logger.warning("Falha ao criar evento no Calendar: %s", e)

            db.add(appt)
            lead.commercial_status = "proposal"
            await db.commit()
            await db.refresh(appt)

            appt_id = appt.id
            logger.info(
                "book_appointment OK: appt_id=%s lead_id=%s phone=%s channel=%s scheduled_at=%s",
                appt_id, lead.id, lead.phone, channel, _parsed.isoformat(),
            )

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
