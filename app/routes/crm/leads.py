"""Endpoints CRM — Leads."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lead
from app.db.session import get_db

router = APIRouter(prefix="/api/leads", tags=["CRM · Leads"])


# ── Schemas ────────────────────────────────────────────────────────────────

_EMPTY = {"none", "null", "undefined", "unknown", ""}


def _clean(v: str | None) -> str | None:
    """Converte strings falsas (None, null, unknown…) em None real."""
    if v is None:
        return None
    stripped = v.strip()
    return None if stripped.lower() in _EMPTY else stripped


class LeadOut(BaseModel):
    id: str
    phone: str
    name: str | None
    email: str | None
    platform: str | None
    case_type: str | None
    case_description: str | None
    monthly_loss_estimate: float | None
    qualification_score: int
    qualification_level: str | None
    qualification_signals: dict | None
    commercial_status: str
    source: str
    assigned_to: str | None
    ai_active: bool
    ai_silenced_until: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    commercial_status: str | None = None
    assigned_to: str | None = None
    ai_active: bool | None = None
    platform: str | None = None
    case_type: str | None = None
    case_description: str | None = None
    qualification_score: int | None = None
    qualification_level: str | None = None
    qualification_signals: dict | None = None
    notes: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: object) -> str | None:
        return _clean(str(v)) if v is not None else None


class LeadCreate(BaseModel):
    phone: str
    name: str | None = None
    source: str = "unknown"
    platform: str | None = None
    case_type: str | None = None
    case_description: str | None = None
    qualification_score: int = 0
    qualification_level: str | None = None
    qualification_signals: dict | None = None
    commercial_status: str = "new"
    monthly_loss_estimate: float | None = None

    @field_validator("name", "platform", "case_type", mode="before")
    @classmethod
    def sanitize_strings(cls, v: object) -> str | None:
        return _clean(str(v)) if v is not None else None


# ── Helpers ────────────────────────────────────────────────────────────────

def lead_to_dict(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "phone": lead.phone,
        "name": lead.name,
        "email": lead.email,
        "platform": lead.platform,
        "case_type": lead.case_type,
        "case_description": lead.case_description,
        "monthly_loss_estimate": lead.monthly_loss_estimate,
        "qualification_score": lead.qualification_score,
        "qualification_level": lead.qualification_level,
        "qualification_signals": lead.qualification_signals,
        "commercial_status": lead.commercial_status,
        "source": lead.source,
        "assigned_to": lead.assigned_to,
        "ai_active": lead.ai_active,
        "ai_silenced_until": lead.ai_silenced_until,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
async def list_leads(
    status: str | None = Query(None),
    source: str | None = Query(None),
    level: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Lista leads com filtros opcionais."""
    q = select(Lead).order_by(Lead.updated_at.desc())

    if status:
        q = q.where(Lead.commercial_status == status)
    if source:
        q = q.where(Lead.source == source)
    if level:
        q = q.where(Lead.qualification_level == level)
    if search:
        q = q.where(
            Lead.name.ilike(f"%{search}%") | Lead.phone.ilike(f"%{search}%")
        )

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()

    result = await db.execute(q.limit(limit).offset(offset))
    leads = result.scalars().all()

    return {"items": [lead_to_dict(l) for l in leads], "total": total}


@router.get("/funnel")
async def leads_funnel(db: AsyncSession = Depends(get_db)):
    """Agrupa leads por estágio do pipeline para o funil CRM."""
    stages_order = ["new", "contacted", "qualified", "proposal", "won", "follow_up", "lost"]

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


@router.get("/{lead_id}")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Retorna detalhes de um lead."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return lead_to_dict(lead)


@router.post("", status_code=201)
async def create_lead(body: LeadCreate, db: AsyncSession = Depends(get_db)):
    """Cria um novo lead (chamado pelo agente após primeira mensagem)."""
    existing = await db.execute(select(Lead).where(Lead.phone == body.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Lead com este telefone já existe")

    lead = Lead(**body.model_dump())
    db.add(lead)
    await db.flush()
    return lead_to_dict(lead)


@router.patch("/{lead_id}")
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Atualiza campos do lead (status, IA toggle, dados)."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(lead, field, value)

    lead.updated_at = datetime.now(timezone.utc)
    return lead_to_dict(lead)


@router.post("/{lead_id}/toggle-ai")
async def toggle_ai(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Liga ou desliga a IA para este lead."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    lead.ai_active = not lead.ai_active
    lead.updated_at = datetime.now(timezone.utc)

    return {"lead_id": lead_id, "ai_active": lead.ai_active}


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Remove um lead e todos os seus dados relacionados."""
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    await db.delete(lead)
    return None
