"""Evolution API — cliente WhatsApp.

Em desenvolvimento: defina MOCK_SERVICES=true no .env para logar as mensagens
no console sem enviar nada pelo WhatsApp real.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_MOCK = os.environ.get("MOCK_SERVICES", "false").lower() == "true"


class WhatsAppService:
    """Cliente para Evolution API (self-hosted)."""

    def __init__(self) -> None:
        if not _MOCK:
            self.base_url = os.environ["EVOLUTION_API_URL"].rstrip("/")
            self.api_key = os.environ["EVOLUTION_API_KEY"]
            self.instance = os.environ["EVOLUTION_INSTANCE_NAME"]
            self._headers = {"apikey": self.api_key, "Content-Type": "application/json"}

    async def send_text(self, phone: str, message: str) -> dict:
        if _MOCK:
            logger.info("[MOCK] WhatsApp → %s: %s", phone, message[:120])
            return {"status": "mock_sent", "phone": phone}

        """Envia mensagem de texto via WhatsApp."""
        url = f"{self.base_url}/message/sendText/{self.instance}"
        payload = {"number": phone, "text": message}

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            return response.json()

    async def notify_escalation(self, lead_id: str, reason: str, urgency: str) -> None:
        if _MOCK:
            logger.info("[MOCK] Escalação lead=%s urgency=%s reason=%s", lead_id, urgency, reason)
            return

        """Notifica advogado sobre escalação via WhatsApp."""
        lawyer_phone = os.environ.get("ESCALATION_PHONE_NUMBER")
        if not lawyer_phone:
            return

        urgency_emoji = {"low": "🟡", "normal": "🔵", "high": "🟠", "critical": "🔴"}.get(urgency, "⚪")
        message = (
            f"{urgency_emoji} *Escalação {urgency.upper()}*\n\n"
            f"Lead: {lead_id}\n"
            f"Motivo: {reason}\n\n"
            f"Acesse o CRM para continuar o atendimento."
        )
        await self.send_text(lawyer_phone, message)
