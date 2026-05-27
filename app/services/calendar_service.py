"""Google Calendar API — service account com domain-wide delegation.

Em desenvolvimento: defina MOCK_SERVICES=true no .env para retornar dados falsos
sem precisar de credenciais Google.
"""

import logging
import os
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

# google-auth + googleapiclient são instalados via pyproject.toml
# google-auth-httplib2, google-auth-oauthlib, google-api-python-client

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("America/Sao_Paulo")
BUSINESS_START = time(8, 0)
BUSINESS_END = time(18, 0)
SLOT_INTERVAL_MINUTES = 30

_MOCK = os.environ.get("MOCK_SERVICES", "false").lower() == "true"


class CalendarService:
    """Cliente Google Calendar usando service account."""

    def __init__(self) -> None:
        self._service = None  # lazy init

    def _build_service(self) -> Any:
        """Constrói o cliente autenticado via service account."""
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"],
            scopes=["https://www.googleapis.com/auth/calendar"],
        ).with_subject(os.environ["GOOGLE_CALENDAR_SUBJECT_EMAIL"])

        return build("calendar", "v3", credentials=credentials)

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = self._build_service()
        return self._service

    async def get_available_slots(self, date_str: str, duration_minutes: int = 60) -> list[str]:
        if _MOCK:
            logger.info("[MOCK] get_available_slots(%s)", date_str)
            all_slots = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"]
            now = datetime.now(tz=TIMEZONE)
            target = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Remove slots já passados (margem de 5min) se for hoje
            if target == now.date():
                cutoff = now + timedelta(minutes=5)
                available = [
                    s for s in all_slots
                    if datetime.combine(target, time.fromisoformat(s), tzinfo=TIMEZONE) > cutoff
                ]
            else:
                available = list(all_slots)

            # Remove slots já agendados no banco CRM
            try:
                from datetime import timezone as _utc
                from app.db.session import AsyncSessionLocal
                from app.db.models import Appointment as ApptModel
                from sqlalchemy import select as sa_select

                # Usa UTC naive para comparação — compatível com como o Postgres armazena
                day_start_utc = datetime.combine(target, time(0, 0), tzinfo=TIMEZONE).astimezone(_utc).replace(tzinfo=None)
                day_end_utc   = datetime.combine(target, time(23, 59), tzinfo=TIMEZONE).astimezone(_utc).replace(tzinfo=None)

                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        sa_select(ApptModel.scheduled_at).where(
                            ApptModel.scheduled_at >= day_start_utc,
                            ApptModel.scheduled_at <= day_end_utc,
                            ApptModel.status.notin_(["cancelled"]),
                        )
                    )
                    booked = set()
                    for row in result.all():
                        dt = row[0]
                        if dt is None:
                            continue
                        # Trata tanto naive (UTC do banco) quanto aware
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=_utc)
                        booked.add(dt.astimezone(TIMEZONE).strftime("%H:%M"))

                    available = [s for s in available if s not in booked]
                    logger.info("[MOCK] slots booked on %s: %s | available: %s", date_str, booked, available)
            except Exception as e:
                logger.warning("[MOCK] Falha ao verificar agendamentos no banco: %s", e)

            logger.info("[MOCK] Slots disponíveis para %s: %s", date_str, available)
            return available

        """Retorna lista de horários disponíveis (HH:MM) para a data."""
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        calendar_id = os.environ.get("LAWYER_CALENDAR_ID", "primary")

        time_min = datetime.combine(target_date, BUSINESS_START, tzinfo=TIMEZONE).isoformat()
        time_max = datetime.combine(target_date, BUSINESS_END, tzinfo=TIMEZONE).isoformat()

        body = {"timeMin": time_min, "timeMax": time_max, "items": [{"id": calendar_id}]}
        result = self.service.freebusy().query(body=body).execute()
        busy_periods = result["calendars"][calendar_id]["busy"]

        slots = []
        cursor = datetime.combine(target_date, BUSINESS_START, tzinfo=TIMEZONE)
        end_boundary = datetime.combine(target_date, BUSINESS_END, tzinfo=TIMEZONE)

        while cursor + timedelta(minutes=duration_minutes) <= end_boundary:
            slot_end = cursor + timedelta(minutes=duration_minutes)
            if not self._overlaps(cursor, slot_end, busy_periods):
                slots.append(cursor.strftime("%H:%M"))
            cursor += timedelta(minutes=SLOT_INTERVAL_MINUTES)

        return slots

    def _overlaps(self, start: datetime, end: datetime, busy: list[dict]) -> bool:
        for period in busy:
            b_start = datetime.fromisoformat(period["start"])
            b_end = datetime.fromisoformat(period["end"])
            if start < b_end and end > b_start:
                return True
        return False

    async def create_appointment(
        self,
        lead_id: str,
        slot_datetime: str,
        client_name: str,
        client_email: str = "",
        appointment_type: str = "initial_consultation",
    ) -> dict:
        if _MOCK:
            logger.info("[MOCK] create_appointment(lead=%s, slot=%s)", lead_id, slot_datetime)
            try:
                dt = datetime.fromisoformat(slot_datetime).replace(tzinfo=TIMEZONE)
                formatted = dt.strftime("%d/%m/%Y às %H:%M")
            except Exception:
                formatted = slot_datetime
            return {
                "event_id": f"mock-event-{lead_id}",
                "meet_link": "https://meet.google.com/mock-drx-test",
                "formatted_datetime": formatted,
            }

        """Cria evento no Google Calendar e retorna dados do evento."""
        import uuid

        calendar_id = os.environ.get("LAWYER_CALENDAR_ID", "primary")
        lawyer_email = os.environ["GOOGLE_CALENDAR_SUBJECT_EMAIL"]
        duration = int(os.environ.get("APPOINTMENT_DURATION_MINUTES", "60"))

        start_dt = datetime.fromisoformat(slot_datetime).replace(tzinfo=TIMEZONE)
        end_dt = start_dt + timedelta(minutes=duration)

        attendees = [{"email": lawyer_email}]
        if client_email:
            attendees.append({"email": client_email})

        event_body: dict = {
            "summary": f"Consulta — {client_name}",
            "description": f"Lead ID: {lead_id} | Tipo: {appointment_type}",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/Sao_Paulo"},
            "attendees": attendees,
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 1440},
                    {"method": "popup", "minutes": 60},
                ],
            },
        }

        created = self.service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates="all",
        ).execute()

        meet_link = (
            created.get("conferenceData", {})
            .get("entryPoints", [{}])[0]
            .get("uri", "")
        )

        return {
            "event_id": created["id"],
            "meet_link": meet_link,
            "formatted_datetime": start_dt.strftime("%d/%m/%Y às %H:%M"),
        }
