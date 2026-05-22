"""Model: Lead."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    cpf: Mapped[str | None] = mapped_column(String(14))
    source: Mapped[str] = mapped_column(String(50), default="whatsapp")
    case_type: Mapped[str | None] = mapped_column(String(100))
    case_description: Mapped[str | None] = mapped_column(Text)
    qualification_score: Mapped[int] = mapped_column(Integer, default=0)
    qualification_level: Mapped[str | None] = mapped_column(String(20))
    commercial_status: Mapped[str] = mapped_column(String(50), default="new")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
