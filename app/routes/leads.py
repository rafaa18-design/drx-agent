"""CRUD de leads — CRM DRX."""

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/leads", tags=["leads"])

LeadStatus = Literal["new", "contacted", "qualified", "proposal", "won", "lost"]
QualificationLevel = Literal["hot", "warm", "cold", "disqualified"]


class LeadCreate(BaseModel):
    phone: str
    name: str | None = None
    email: str | None = None
    case_type: str | None = None
    case_description: str | None = None
    source: str = "whatsapp"


class LeadUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    case_type: str | None = None
    commercial_status: LeadStatus | None = None
    assigned_to: uuid.UUID | None = None
    notes: str | None = None


class LeadResponse(BaseModel):
    id: uuid.UUID
    phone: str
    name: str | None
    email: str | None
    case_type: str | None
    qualification_score: int
    qualification_level: str | None
    commercial_status: str
    source: str


@router.get("")
async def list_leads(
    status: LeadStatus | None = Query(default=None),
    level: QualificationLevel | None = Query(default=None),
    assigned_to: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Lista leads com filtros opcionais."""
    # TODO: implementar query no banco com filtros, paginação
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/{lead_id}")
async def get_lead(lead_id: uuid.UUID) -> dict:
    """Retorna detalhes completos do lead: dados, histórico e agendamentos."""
    # TODO: buscar lead + conversations + appointments do banco
    raise HTTPException(status_code=404, detail="Lead not found")


@router.post("", status_code=201)
async def create_lead(body: LeadCreate) -> dict:
    """Cria lead manualmente."""
    # TODO: inserir no banco
    return {"id": str(uuid.uuid4()), **body.model_dump()}


@router.patch("/{lead_id}")
async def update_lead(lead_id: uuid.UUID, body: LeadUpdate) -> dict:
    """Atualiza status, responsável ou dados do lead."""
    # TODO: atualizar no banco
    return {"id": str(lead_id), **body.model_dump(exclude_none=True)}


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: uuid.UUID) -> None:
    """Anonimiza lead (LGPD — soft delete)."""
    # TODO: anonimizar dados pessoais no banco
    pass


@router.get("/{lead_id}/score-breakdown")
async def get_score_breakdown(lead_id: uuid.UUID) -> dict:
    """Retorna histórico de eventos de qualificação do lead."""
    # TODO: buscar qualification_events do banco
    return {"lead_id": str(lead_id), "events": []}
