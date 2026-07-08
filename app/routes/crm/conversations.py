"""Endpoints CRM — Conversas e fila de atendimento humano."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Lead, Message
from app.db.session import get_db

router = APIRouter(prefix="/api/conversations", tags=["CRM · Conversas"])


# ── Schemas ────────────────────────────────────────────────────────────────

class ConversationOut(BaseModel):
    id: str
    lead_id: str
    lead_name: str | None
    lead_phone: str | None
    channel: str
    status: str
    ai_handoff_reason: str | None
    started_at: datetime
    last_message_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class ReplyBody(BaseModel):
    message: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    direction: str
    sender: str
    content_type: str
    content: str | None
    media_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Helpers ────────────────────────────────────────────────────────────────

def conv_to_dict(c: Conversation, lead: Lead | None = None) -> dict:
    return {
        "id": c.id,
        "lead_id": c.lead_id,
        "lead_name": lead.name if lead else None,
        "lead_phone": lead.phone if lead else None,
        "channel": c.channel,
        "status": c.status,
        "ai_handoff_reason": c.ai_handoff_reason,
        "started_at": c.started_at,
        "last_message_at": c.last_message_at,
        "closed_at": c.closed_at,
    }


def msg_to_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "direction": m.direction,
        "sender": m.sender,
        "content_type": m.content_type,
        "content": m.content,
        "media_url": m.media_url,
        "created_at": m.created_at,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
async def list_conversations(
    status: str | None = Query(None),
    lead_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Lista conversas — filtro por status permite isolar fila de atendimento humano."""
    from sqlalchemy.orm import joinedload

    q = (
        select(Conversation)
        .options(joinedload(Conversation.lead))
        .order_by(Conversation.last_message_at.desc())
    )

    if status:
        q = q.where(Conversation.status == status)
    if lead_id:
        q = q.where(Conversation.lead_id == lead_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    result = await db.execute(q.limit(limit).offset(offset))
    convs = result.scalars().unique().all()

    return {"items": [conv_to_dict(c, c.lead) for c in convs], "total": total}


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    lead = await db.get(Lead, conv.lead_id)
    return conv_to_dict(conv, lead)


@router.get("/{conv_id}/messages")
async def list_messages(
    conv_id: str,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Histórico de mensagens de uma conversa."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    msgs = result.scalars().all()
    return {"items": [msg_to_dict(m) for m in msgs]}


@router.post("/{conv_id}/reply")
async def reply_conversation(
    conv_id: str,
    body: ReplyBody,
    db: AsyncSession = Depends(get_db),
):
    """Tiago humano responde a uma conversa — salva mensagem e atualiza status."""
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    msg = Message(
        conversation_id=conv_id,
        direction="outbound",
        sender="human",
        content_type="text",
        content=body.message,
    )
    db.add(msg)

    conv.last_message_at = datetime.now(timezone.utc)
    if conv.status == "human_required":
        conv.status = "active"

    await db.flush()
    return {"ok": True, "message_id": msg.id}


@router.patch("/{conv_id}/status")
async def update_conversation_status(
    conv_id: str,
    status: str = Query(...),
    reason: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza status da conversa (active, human_required, closed)."""
    valid = {"active", "human_required", "closed", "scheduled"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status inválido. Use: {valid}")

    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    conv.status = status
    if reason:
        conv.ai_handoff_reason = reason
    if status == "closed":
        conv.closed_at = datetime.now(timezone.utc)

    return conv_to_dict(conv)
