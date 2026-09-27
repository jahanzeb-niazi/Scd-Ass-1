"""SQLAlchemy ORM mapping. Mirrors alembic/versions/0001_initial_schema.py.

The schema is owned by Alembic: nothing here is ever used to CREATE TABLE.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import Category, Priority, Status, TriagedBy


class Base(DeclarativeBase):
    pass


def _pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    # Store the enum *values* ("in_progress", "llm:gemini"), not member names,
    # and never let SQLAlchemy try to create the type — Alembic owns it.
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
        validate_strings=True,
    )


class ComplaintRow(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[Category] = mapped_column(_pg_enum(Category, "complaint_category"))
    priority: Mapped[Priority] = mapped_column(_pg_enum(Priority, "complaint_priority"))
    status: Mapped[Status] = mapped_column(
        _pg_enum(Status, "complaint_status"), server_default=Status.OPEN.value
    )
    ai_summary: Mapped[str | None] = mapped_column(String(140), nullable=True)
    triaged_by: Mapped[TriagedBy] = mapped_column(_pg_enum(TriagedBy, "triage_source"))
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
