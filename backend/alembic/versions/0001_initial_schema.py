"""Initial schema: complaints table, enums, constraints, indexes, updated_at trigger.

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("water", "electricity", "sanitation", "roads", "streetlights", "other")
PRIORITIES = ("high", "normal", "low")
STATUSES = ("open", "in_progress", "resolved", "rejected")
TRIAGE_SOURCES = ("llm:gemini", "llm:groq", "llm:ollama", "rules", "rules:fallback", "simulated")


def upgrade() -> None:
    category = pg.ENUM(*CATEGORIES, name="complaint_category", create_type=False)
    priority = pg.ENUM(*PRIORITIES, name="complaint_priority", create_type=False)
    status = pg.ENUM(*STATUSES, name="complaint_status", create_type=False)
    source = pg.ENUM(*TRIAGE_SOURCES, name="triage_source", create_type=False)
    bind = op.get_bind()
    for e in (category, priority, status, source):
        e.create(bind, checkfirst=True)

    op.create_table(
        "complaints",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("reporter_contact", sa.String(200), nullable=True),
        sa.Column("category", category, nullable=False),
        sa.Column("priority", priority, nullable=False),
        sa.Column("status", status, nullable=False, server_default="open"),
        sa.Column("ai_summary", sa.String(140), nullable=True),
        sa.Column("triaged_by", source, nullable=False),
        sa.Column("triage_latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        # Length rules enforced in the database as well as the app.
        sa.CheckConstraint("char_length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_len"),
        sa.CheckConstraint("char_length(location) BETWEEN 3 AND 200",
                           name="ck_complaints_location_len"),
        sa.CheckConstraint("ai_summary IS NULL OR char_length(ai_summary) <= 140",
                           name="ck_complaints_summary_len"),
        sa.CheckConstraint("triage_latency_ms >= 0", name="ck_complaints_latency_nonneg"),
    )

    # Serves: GET /api/complaints?status=open&priority=high (the operator's
    # "what is on fire right now" filter) — equality on the leading columns.
    op.create_index("ix_complaints_status_priority", "complaints", ["status", "priority"])
    # Serves: ORDER BY created_at DESC LIMIT/OFFSET on every dashboard page load.
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])

    # updated_at is maintained by the database, so no code path can forget it.
    op.execute(
        """
        CREATE FUNCTION complaints_touch_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER complaints_touch_updated_at
        BEFORE UPDATE ON complaints
        FOR EACH ROW EXECUTE FUNCTION complaints_touch_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS complaints_touch_updated_at ON complaints")
    op.execute("DROP FUNCTION IF EXISTS complaints_touch_updated_at()")
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")
    for name in ("triage_source", "complaint_status", "complaint_priority", "complaint_category"):
        op.execute(f"DROP TYPE IF EXISTS {name}")
