"""SQLAlchemy ORM models para o CRM DRX Advogados."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Lead
# ─────────────────────────────────────────────────────────────────────────────

class Lead(Base):
    """Representa um lead qualificado pelo agente Tiago."""
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Plataforma e problema
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)   # instagram, tiktok, youtube
    case_type: Mapped[str | None] = mapped_column(String(50), nullable=True)   # ban, restriction, block
    case_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_loss_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Qualificação
    qualification_score: Mapped[int] = mapped_column(Integer, default=0)
    qualification_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # hot, warm, cold, disqualified, auto_meeting
    qualification_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Pipeline comercial
    commercial_status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    # new → contacted → qualified → proposal → won | lost
    source: Mapped[str] = mapped_column(String(30), default="unknown")
    # ad | referral | existing_client | unknown
    assigned_to: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Toggle IA
    ai_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_silenced_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Follow-up pós-reunião (FU01=1, FU02=2, FU03=3)
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    follow_up_last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now())

    # Relacionamentos
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship("Appointment", back_populates="lead", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# Conversation
# ─────────────────────────────────────────────────────────────────────────────

class Conversation(Base):
    """Conversa entre o lead e o agente/humano."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    # active | human_required | closed | scheduled
    ai_handoff_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# Message
# ─────────────────────────────────────────────────────────────────────────────

class Message(Base):
    """Mensagem individual dentro de uma conversa."""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10))       # inbound | outbound
    sender: Mapped[str] = mapped_column(String(10))           # client | ai | human
    content_type: Mapped[str] = mapped_column(String(20), default="text")  # text | audio | image | document
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


# ─────────────────────────────────────────────────────────────────────────────
# Lawyer
# ─────────────────────────────────────────────────────────────────────────────

class Lawyer(Base):
    """Advogado do escritório — dono de uma agenda Google conectada via OAuth."""
    __tablename__ = "lawyers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # username deve casar com uma chave de AUTH_USERS — é assim que o login do CRM
    # resolve "qual advogado sou eu" ao clicar em "Conectar Google Calendar".

    calendar_id: Mapped[str] = mapped_column(String(200), default="primary")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # Advogado usado pelo Tiago quando agenda pelo WhatsApp (sem atribuição manual ainda).

    google_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_account_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now())

    appointments: Mapped[list["Appointment"]] = relationship("Appointment", back_populates="lawyer")


# ─────────────────────────────────────────────────────────────────────────────
# Appointment
# ─────────────────────────────────────────────────────────────────────────────

class Appointment(Base):
    """Agendamento de reunião com advogado."""
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    lawyer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("lawyers.id", ondelete="SET NULL"), nullable=True, index=True)
    google_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_meet_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    # scheduled | confirmed | cancelled | completed | no_show
    appointment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

    lead: Mapped["Lead"] = relationship("Lead", back_populates="appointments")
    lawyer: Mapped["Lawyer | None"] = relationship("Lawyer", back_populates="appointments")
