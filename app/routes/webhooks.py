"""Webhook WhatsApp — recebe eventos da Evolution API."""

import hashlib
import hmac
import os

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.observability import get_logger

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


async def _process_message(payload: dict) -> None:
    """Processa mensagem recebida de forma assíncrona."""
    # TODO: extrair phone, message, tipo (text/audio/image)
    # TODO: criar ou buscar lead pelo phone
    # TODO: criar registro de mensagem no banco
    # TODO: encaminhar para agent loop via /run
    event_type = payload.get("event", "unknown")
    logger.info(f"WhatsApp event received: {event_type}")


def _verify_signature(body: bytes, signature: str) -> bool:
    secret = os.environ.get("WHATSAPP_WEBHOOK_SECRET", "")
    if not secret:
        return True  # desabilitado se não configurado
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_signature: str = Header(default=""),
) -> dict:
    """Recebe eventos da Evolution API (mensagens, status, conexão)."""
    body = await request.body()

    if not _verify_signature(body, x_webhook_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    background_tasks.add_task(_process_message, payload)

    # Retorna 200 imediatamente — processamento é assíncrono
    return {"status": "received"}
