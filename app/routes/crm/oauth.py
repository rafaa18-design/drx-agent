"""Endpoints CRM — Conexão OAuth do Google Calendar por advogado."""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_username
from app.db.models import Lawyer
from app.db.session import get_db
from app.observability import get_logger
from app.storage import cache_delete, cache_get, cache_set

logger = get_logger(__name__)

router = APIRouter(tags=["CRM · Google Calendar (OAuth)"])

_STATE_TTL = 600  # 10 minutos — tempo de vida do fluxo de consentimento


def _crm_frontend_url() -> str:
    import os
    return os.environ.get("CRM_FRONTEND_URL", "http://localhost:3000")


def lawyer_to_dict(lw: Lawyer) -> dict:
    return {
        "id": lw.id,
        "name": lw.name,
        "email": lw.email,
        "username": lw.username,
        "is_default": lw.is_default,
        "google_connected": bool(lw.google_refresh_token_encrypted),
        "google_account_email": lw.google_account_email,
    }


@router.get("/api/lawyers")
async def list_lawyers(db: AsyncSession = Depends(get_db)):
    """Lista advogados — nunca expõe o refresh token."""
    result = await db.execute(select(Lawyer).order_by(Lawyer.name))
    return [lawyer_to_dict(lw) for lw in result.scalars().all()]


@router.post("/api/lawyers/{lawyer_id}/disconnect")
async def disconnect_lawyer(
    lawyer_id: str,
    username: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    lawyer = await db.get(Lawyer, lawyer_id)
    if not lawyer:
        raise HTTPException(status_code=404, detail="Advogado não encontrado")
    if lawyer.username != username:
        raise HTTPException(status_code=403, detail="Só o próprio advogado pode desconectar sua conta")

    lawyer.google_refresh_token_encrypted = None
    lawyer.google_account_email = None
    lawyer.google_connected_at = None
    await db.commit()
    return lawyer_to_dict(lawyer)


@router.get("/api/oauth/google/start")
async def start_google_oauth(
    username: str = Depends(get_current_username),
    db: AsyncSession = Depends(get_db),
):
    """Gera a URL de consentimento do Google para o advogado logado conectar sua agenda.

    Retorna JSON (não redireciona direto) porque o frontend precisa mandar o
    header Authorization nesta chamada — um redirect de navegação não carrega
    esse header. O frontend navega para a authorization_url só depois.
    """
    from app.services.google_oauth_service import get_authorization_url

    result = await db.execute(select(Lawyer).where(Lawyer.username == username))
    lawyer = result.scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Usuário não está vinculado a um advogado cadastrado")

    state = secrets.token_urlsafe(32)
    await cache_set(f"oauth:state:{state}", lawyer.id, ttl=_STATE_TTL)

    return {"authorization_url": get_authorization_url(state)}


@router.get("/api/oauth/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Callback do Google — recebe o code, troca por tokens e salva no advogado.

    Sem auth via Bearer aqui: quem chama é o navegador do advogado, redirecionado
    pelo próprio Google (sem headers customizados). A segurança vem do `state`
    de uso único guardado no Redis no passo /start.
    """
    from app.services.google_oauth_service import encrypt_refresh_token, exchange_code

    frontend = _crm_frontend_url()

    lawyer_id = await cache_get(f"oauth:state:{state}")
    if not lawyer_id:
        return RedirectResponse(f"{frontend}/settings?google=error&reason=invalid_state")
    await cache_delete(f"oauth:state:{state}")

    lawyer = await db.get(Lawyer, lawyer_id)
    if not lawyer:
        return RedirectResponse(f"{frontend}/settings?google=error&reason=lawyer_not_found")

    try:
        tokens = exchange_code(code)
        if not tokens.get("refresh_token"):
            # O Google só devolve refresh_token com prompt=consent (já forçado no
            # /start) — se ainda assim vier vazio, algo na configuração está errado.
            raise RuntimeError("Google não retornou refresh_token")

        lawyer.google_refresh_token_encrypted = encrypt_refresh_token(tokens["refresh_token"])
        lawyer.google_account_email = tokens.get("account_email")
        lawyer.google_connected_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception as e:
        logger.error(f"Falha ao conectar Google Calendar do advogado {lawyer_id}: {e}")
        return RedirectResponse(f"{frontend}/settings?google=error&reason=exchange_failed")

    return RedirectResponse(f"{frontend}/settings?google=success")
