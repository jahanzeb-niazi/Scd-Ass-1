"""initial schema — complaints table

Revision ID: 0001
Revises:
Create Date: TODO(you): fill in when you generate this for real

TODO(you): this file is a hand-written STARTING POINT, not a generated
migration. Once your app/db/models.py is finalized (including the indexes
noted in that file's TODOs), regenerate this properly, e.g. with
`alembic revision --autogenerate -m "initial schema"`, and replace this file's
body with the real output. Do not hand-edit a generated migration and a
hand-written skeleton into an inconsistent state.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "complaints",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("reporter_contact", sa.String(), nullable=True),
        sa.Column(
            "category",
            sa.Enum("water", "electricity", "sanitation", "roads", "streetlights", "other",
                    name="category_enum"),
            nullable=False,
        ),
        sa.Column("priority", sa.Enum("high", "normal", "low", name="priority_enum"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "resolved", "rejected", name="status_enum"),
            nullable=False, server_default="open",
        ),
        sa.Column("ai_summary", sa.String(length=140), nullable=True),
        sa.Column("triaged_by", sa.String(), nullable=False),
        sa.Column("triage_latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            onupdate=sa.func.now(), nullable=False,
        ),
        # TODO(you): DB-level CHECK constraints for text/location length (§2.3:
        # "enforced in the DB as well as the app") — add via sa.CheckConstraint(...).
    )

    # TODO(you): create the two required indexes here and justify each with a
    # named query in docs/ENGINEERING-NOTES.md (§2.3):
    #   op.create_index("ix_complaints_status_priority", "complaints", ["status", "priority"])
    #   op.create_index("ix_complaints_created_at", "complaints", ["created_at"])


def downgrade() -> None:
    op.drop_table("complaints")
    # TODO(you): drop the enum types too (Postgres doesn't drop them automatically
    # when you drop the table) — sa.Enum(name=...).drop(op.get_bind(), checkfirst=True)
    # for each of category_enum / priority_enum / status_enum.
