"""Tools de WhatsApp e escalação humana para DRX."""

from app.runtime import RetryAgentRun, RunContext, tool

VALID_URGENCIES = {"low", "normal", "high", "critical"}


@tool
async def send_whatsapp_message(phone: str, message: str) -> str:
    """Envia uma mensagem via WhatsApp para o número informado.

    Use para confirmações, lembretes ou mensagens proativas.

    Args:
        phone: Número no formato internacional (ex: +5511999999999).
        message: Texto da mensagem.

    Returns:
        Confirmação de envio.
    """
    from app.services.whatsapp_service import WhatsAppService

    try:
        service = WhatsAppService()
        await service.send_text(phone, message)
        return f"Mensagem enviada para {phone}."
    except Exception as e:
        raise RetryAgentRun(f"Erro ao enviar mensagem: {e}")


@tool
async def escalate_to_human(
    run_context: RunContext,
    lead_id: str,
    reason: str,
    urgency: str = "normal",
) -> str:
    """Transfere a conversa para atendimento humano.

    Use quando: cliente solicitar advogado, prazo judicial < 48h,
    caso fora do escopo, ou 3+ tentativas sem resolução.

    Args:
        lead_id: ID do lead.
        reason: Motivo da escalação (ex: "prazo judicial urgente").
        urgency: Nível de urgência (low, normal, high, critical).

    Returns:
        Confirmação e próximos passos para o cliente.
    """
    if urgency not in VALID_URGENCIES:
        raise RetryAgentRun(
            f'Urgência "{urgency}" inválida. Use: {", ".join(sorted(VALID_URGENCIES))}'
        )

    from app.services.whatsapp_service import WhatsAppService

    run_context.session_state["escalated"] = True
    run_context.session_state["escalation"] = {
        "lead_id": lead_id,
        "reason": reason,
        "urgency": urgency,
    }

    # Notificar advogado responsável
    try:
        service = WhatsAppService()
        await service.notify_escalation(lead_id=lead_id, reason=reason, urgency=urgency)
    except Exception:
        pass  # Falha silenciosa — a escalação já está registrada

    wait_map = {"low": "até 24 horas", "normal": "em breve", "high": "em até 1 hora", "critical": "imediatamente"}
    return (
        f"Entendido! Um dos nossos advogados entrará em contato com você {wait_map[urgency]}. "
        f"Obrigado pela paciência."
    )
