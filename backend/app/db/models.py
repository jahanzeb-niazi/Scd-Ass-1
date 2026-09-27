"""
ORM model for the `complaints` table. Schema is owned by Alembic migrations
(alembic/versions/) — this class must match the latest migration exactly.
NEVER create tables from this file at app startup (§2.3: "no CREATE TABLE in
application startup code, ever").

Column list is verbatim from the assignment's minimum-schema table (§2.3).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Category(str, enum.Enum):
    WATER = "water"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    ROADS = "roads"
    STREETLIGHTS = "streetlights"
    OTHER = "other"


class Priority(str, enum.Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Status(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class TriagedBy(str, enum.Enum):
    LLM_GROQ = "llm:groq"
    LLM_OLLAMA = "llm:ollama"
    RULES = "rules"
    RULES_FALLBACK = "rules:fallback"


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)  # 10-2000 chars, DB + app enforced
    location: Mapped[str] = mapped_column(String(200), nullable=False)  # 3-200 chars
    reporter_contact: Mapped[str | None] = mapped_column(String, nullable=True)

    category: Mapped[Category] = mapped_column(Enum(Category, name="category_enum"), nullable=False)
    priority: Mapped[Priority] = mapped_column(Enum(Priority, name="priority_enum"), nullable=False)
    status: Mapped[Status] = mapped_column(
        Enum(Status, name="status_enum"), nullable=False, default=Status.OPEN
    )

    ai_summary: Mapped[str | None] = mapped_column(String(140), nullable=True)
    triaged_by: Mapped[str] = mapped_column(String, nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # TODO(you): add __table_args__ with Index("ix_status_priority", "status", "priority")
    # and Index("ix_created_at", "created_at") — then write the matching Alembic migration.
    # Justify each index with a named query in docs/ENGINEERING-NOTES.md (§2.3 requirement).
