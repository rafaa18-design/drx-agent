"""Endpoints de conversas — fila de handoff humano."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

ConversationStatus = Literal["active", "human_required", "closed", "scheduled"]

# Registry simples de conexões WebSocket ativas
_ws_connections: list[WebSocket] = []


class HumanReply(BaseModel):
    message: str


class ConversationStatusUpdate(BaseModel):
    status: ConversationStatus
    assigned_to: uuid.UUID | None = None


@router.get("")
async def list_conversations(
    status: ConversationStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Lista conversas. Sem filtro de status retorna fila human_required."""
    # TODO: query no banco
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID) -> dict:
    """Retorna thread completo de mensagens."""
    # TODO: buscar messages do banco
    return {"id": str(conversation_id), "messages": []}


@router.post("/{conversation_id}/reply")
async def human_reply(conversation_id: uuid.UUID, body: HumanReply) -> dict:
    """Advogado envia mensagem via WhatsApp na conversa."""
    # TODO: buscar phone do lead, enviar via WhatsApp, registrar no banco
    return {"status": "sent", "conversation_id": str(conversation_id)}


@router.patch("/{conversation_id}/status")
async def update_conversation_status(conversation_id: uuid.UUID, body: ConversationStatusUpdate) -> dict:
    """Fecha, reabre ou reatribui uma conversa."""
    # TODO: atualizar no banco + notificar via WS
    return {"id": str(conversation_id), **body.model_dump(exclude_none=True)}


@router.websocket("/ws/conversations")
async def conversations_ws(websocket: WebSocket) -> None:
    """WebSocket para atualizações em tempo real da fila de conversas."""
    await websocket.accept()
    _ws_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # mantém conexão aberta
    except WebSocketDisconnect:
        _ws_connections.remove(websocket)


async def broadcast_conversation_update(payload: dict) -> None:
    """Emite atualização para todos os clientes WS conectados."""
    dead = []
    for ws in _ws_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_connections.remove(ws)
