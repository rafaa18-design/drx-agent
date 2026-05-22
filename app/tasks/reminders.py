"""Tasks de lembrete de consulta — T-24h e T-1h."""

# Requer Celery configurado com Redis broker.
# Ativar com: celery -A app.tasks.reminders worker --beat

from datetime import datetime, timedelta

# from celery import Celery
# app = Celery("drx", broker=os.environ["CELERY_BROKER_URL"])


async def schedule_reminders(appointment_id: str, scheduled_at: datetime, phone: str, client_name: str) -> None:
    """Agenda envio de lembretes para T-24h e T-1h antes da consulta."""
    reminders = [
        (scheduled_at - timedelta(hours=24), "24 horas"),
        (scheduled_at - timedelta(hours=1), "1 hora"),
    ]

    for send_at, label in reminders:
        if send_at > datetime.utcnow():
            await _queue_reminder(appointment_id, phone, client_name, send_at, label)


async def _queue_reminder(
    appointment_id: str,
    phone: str,
    client_name: str,
    send_at: datetime,
    label: str,
) -> None:
    """Enfileira task de lembrete no broker."""
    # TODO: implementar com Celery Beat ou ARQ
    # send_reminder_task.apply_async(
    #     args=[appointment_id, phone, client_name, label],
    #     eta=send_at,
    # )
    pass


async def send_reminder(appointment_id: str, phone: str, client_name: str, label: str) -> None:
    """Envia lembrete via WhatsApp."""
    from app.services.whatsapp_service import WhatsAppService

    message = (
        f"Olá, {client_name}! "
        f"Lembramos que você tem uma consulta agendada com a DRX Advogados em {label}. "
        f"Caso precise reagendar, responda esta mensagem."
    )
    service = WhatsAppService()
    await service.send_text(phone, message)
