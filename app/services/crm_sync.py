"""Sincroniza cada turno de conversa com o CRM (leads, conversations, messages).

Roda após toda execução do agente, independente das tools chamadas pelo LLM —
garante que toda conversa apareça no dashboard, mesmo que o modelo não chame
get_lead_context (ex: respostas curtas a saudações).
"""

import logging
import re
from datetime import datetime, timezone

from app.db.models import Conversation, Lead, Message
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def _is_valid_phone(value: str) -> bool:
    return len(re.sub(r"\D", "", value or "")) >= 8


async def sync_conversation_turn(
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    session_state: dict | None = None,
) -> None:
    """Persiste o turno (mensagem do lead + resposta do agente) no banco do CRM."""
    if not _is_valid_phone(conversation_id):
        return

    session_state = session_state or {}

    try:
        async with AsyncSessionLocal() as db:
            lead = None
            db_lead_id = session_state.get("db_lead_id")
            if db_lead_id:
                lead = await db.get(Lead, db_lead_id)
            if lead is None:
                from sqlalchemy import select as sa_select

                res = await db.execute(
                    sa_select(Lead).where(Lead.phone == conversation_id)
                )
                lead = res.scalar_one_or_none()
            if lead is None:
                lead = Lead(
                    phone=conversation_id,
                    name=session_state.get("client_name"),
                    source=session_state.get("lead_source", "unknown"),
                    commercial_status="new",
                )
                db.add(lead)
                await db.flush()

            from sqlalchemy import select as sa_select

            res = await db.execute(
                sa_select(Conversation)
                .where(Conversation.lead_id == lead.id, Conversation.status == "active")
                .order_by(Conversation.started_at.desc())
            )
            conversation = res.scalars().first()
            if conversation is None:
                conversation = Conversation(lead_id=lead.id, channel="whatsapp", status="active")
                db.add(conversation)
                await db.flush()

            now = datetime.now(timezone.utc)
            if user_text:
                db.add(Message(
                    conversation_id=conversation.id,
                    direction="inbound",
                    sender="client",
                    content_type="text",
                    content=user_text,
                ))
            if assistant_text:
                db.add(Message(
                    conversation_id=conversation.id,
                    direction="outbound",
                    sender="ai",
                    content_type="text",
                    content=assistant_text,
                ))
            conversation.last_message_at = now

            await db.commit()
    except Exception as e:
        logger.warning("Erro ao sincronizar conversa com o CRM: %s", e)
