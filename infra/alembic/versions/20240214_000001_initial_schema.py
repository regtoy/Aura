"""Initial database schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20240214_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("requester", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "ticket_audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "allowed_domains",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "confidence_stats",
        sa.Column("metric", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rolling_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rolling_threshold", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=True, unique=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("roles", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("confidence_stats")
    op.drop_table("allowed_domains")
    op.drop_table("ticket_audit_logs")
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
