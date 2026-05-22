"""Cache temporário de imagens recebidas durante execuções do agente.

TTL de 30 minutos por conversa. Máximo de 200 conversas simultâneas.
Limpeza automática a cada inserção — sem background tasks.
"""
from __future__ import annotations

import time
from typing import NamedTuple

_TTL_SECONDS = 30 * 60   # 30 minutos
_MAX_CONVERSATIONS = 200  # entradas máximas no dict


class ImageEntry(NamedTuple):
    data: bytes
    mime_type: str
    filename: str
    stored_at: float  # timestamp unix


# conversation_id -> lista de imagens (máx 3 por conversa)
_store: dict[str, list[ImageEntry]] = {}


def _evict_expired() -> None:
    """Remove entradas com TTL expirado. Chamado a cada inserção."""
    cutoff = time.monotonic() - _TTL_SECONDS
    expired = [cid for cid, entries in _store.items() if entries[-1].stored_at < cutoff]
    for cid in expired:
        del _store[cid]

    # Se ainda estiver cheio, remove as entradas mais antigas
    if len(_store) > _MAX_CONVERSATIONS:
        oldest = sorted(_store, key=lambda cid: _store[cid][-1].stored_at)
        for cid in oldest[:len(_store) - _MAX_CONVERSATIONS]:
            del _store[cid]


def store_image(conversation_id: str, data: bytes, mime_type: str, filename: str) -> None:
    """Armazena imagem com TTL. Mantém as últimas 3 por conversa."""
    _evict_expired()
    entry = ImageEntry(data, mime_type, filename, stored_at=time.monotonic())
    _store.setdefault(conversation_id, []).append(entry)
    _store[conversation_id] = _store[conversation_id][-3:]


def get_latest_image(conversation_id: str) -> ImageEntry | None:
    """Retorna a imagem mais recente do conversation_id, ou None se expirada/inexistente."""
    entries = _store.get(conversation_id, [])
    if not entries:
        return None
    latest = entries[-1]
    if time.monotonic() - latest.stored_at > _TTL_SECONDS:
        del _store[conversation_id]
        return None
    return latest
