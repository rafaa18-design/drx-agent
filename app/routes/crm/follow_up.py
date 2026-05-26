"""Follow-up pós-reunião — FU01 (dia 3), FU02 (dia 6), FU03 (dia 14)."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Appointment, Lead
from app.db.session import get_db

router = APIRouter(prefix="/api/follow-up", tags=["follow-up"])

# Mensagens definidas no documento DRX_Asani_v3.3.3
_FU_MESSAGES = {
    1: "Boa tarde {nome}, tudo bem? Conseguiu verificar os pontos que alinhamos para dar seguimento no serviço?",
    2: "Boa tarde {nome}. Imagino que esteja na correria, e por isso ainda não retornou. Saiba que estamos disponíveis para regularizar a sua conta, conte conosco.",
    3: "Me parece que regularizar sua conta não é mais uma prioridade para você. Entendo seu momento, mas comunico que iremos encerrar nossos contatos. Não é uma porta que se fecha, saiba que continuamos a disposição.",
}

# Dias mínimos após a reunião para cada follow-up
_FU_MIN_DAYS = {1: 3, 2: 6, 3: 14}


def _days_since(dt: datetime) -> int:
    now = datetime.now(timezone.utc)
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return (now - aware).days


def _build_row(lead: Lead, last_appt: Appointment | None) -> dict[str, Any]:
    next_fu = lead.follow_up_count + 1  # próxima mensagem a enviar (1, 2 ou 3)
    days_since_meeting = _days_since(last_appt.scheduled_at) if last_appt else 0
    min_days = _FU_MIN_DAYS.get(next_fu, 99)
    eligible = days_since_meeting >= min_days

    nome = lead.name or "cliente"
    message_preview = _FU_MESSAGES.get(next_fu, "").format(nome=nome)

    return {
        "lead_id": lead.id,
        "lead_name": lead.name,
        "lead_phone": lead.phone,
        "qualification_score": lead.qualification_score,
        "qualification_level": lead.qualification_level,
        "commercial_status": lead.commercial_status,
        "follow_up_count": lead.follow_up_count,
        "follow_up_last_sent_at": lead.follow_up_last_sent_at.isoformat() if lead.follow_up_last_sent_at else None,
        "next_fu_number": next_fu,
        "next_fu_message": message_preview,
        "days_since_meeting": days_since_meeting,
        "eligible": eligible,
        "last_appointment_at": last_appt.scheduled_at.isoformat() if last_appt else None,
    }


@router.get("")
async def list_follow_ups(db: AsyncSession = Depends(get_db)):
    """Lista leads elegíveis para follow-up, ordenados por score."""
    # Leads em status proposal com menos de 3 follow-ups enviados
    result = await db.execute(
        select(Lead)
        .where(
            Lead.commercial_status == "proposal",
            Lead.follow_up_count < 3,
        )
        .order_by(Lead.qualification_score.desc())
    )
    leads = result.scalars().all()

    rows = []
    for lead in leads:
        # Pega o último agendamento confirmado/completado
        appt_result = await db.execute(
            select(Appointment)
            .where(
                Appointment.lead_id == lead.id,
                Appointment.status.notin_(["cancelled"]),
            )
            .order_by(Appointment.scheduled_at.desc())
            .limit(1)
        )
        last_appt = appt_result.scalar_one_or_none()
        rows.append(_build_row(lead, last_appt))

    return {"items": rows, "total": len(rows)}


@router.post("/{lead_id}/send")
async def mark_follow_up_sent(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Marca o follow-up como enviado — incrementa contador e registra data."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    if lead.follow_up_count >= 3:
        raise HTTPException(status_code=400, detail="Todos os follow-ups já foram enviados")

    lead.follow_up_count += 1
    lead.follow_up_last_sent_at = datetime.now(timezone.utc)

    # Após o 3º follow-up sem resposta → discard
    if lead.follow_up_count >= 3:
        lead.commercial_status = "lost"

    await db.commit()
    return {
        "lead_id": lead_id,
        "follow_up_count": lead.follow_up_count,
        "commercial_status": lead.commercial_status,
        "message": f"FU0{lead.follow_up_count} registrado com sucesso.",
    }


@router.post("/{lead_id}/responded")
async def mark_lead_responded(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Lead respondeu ao follow-up — volta para o funil ativo."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    lead.commercial_status = "qualified"
    lead.ai_active = True
    await db.commit()
    return {
        "lead_id": lead_id,
        "commercial_status": lead.commercial_status,
        "message": "Lead retornou ao funil ativo.",
    }
