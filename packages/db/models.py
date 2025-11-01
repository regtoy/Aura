"""SQLModel table definitions for the Aura data layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return a timezone aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """Generate a random UUID string."""

    return str(uuid.uuid4())


class TicketTable(SQLModel, table=True):
    """Ticket records captured during the HITL workflow."""

    __tablename__ = "tickets"

    id: str = Field(primary_key=True, index=True)
    title: str = Field(sa_column=Column(String(255), nullable=False))
    status: str = Field(sa_column=Column(String(50), nullable=False))
    priority: str = Field(sa_column=Column(String(50), nullable=False))
    requester: str = Field(sa_column=Column(String(255), nullable=False))
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class TicketMessageTable(SQLModel, table=True):
    """Individual messages belonging to a ticket."""

    __tablename__ = "ticket_messages"

    id: str = Field(primary_key=True, index=True)
    ticket_id: str = Field(
        sa_column=Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    )
    author: str = Field(sa_column=Column(String(255), nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    normalized_content: str = Field(sa_column=Column(Text, nullable=False))
    embedding: list[float] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class TicketAuditLogTable(SQLModel, table=True):
    """Audit trail describing discrete ticket actions."""

    __tablename__ = "ticket_audit_logs"

    id: str = Field(primary_key=True, index=True)
    ticket_id: str = Field(
        sa_column=Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    )
    action: str = Field(sa_column=Column(String(100), nullable=False))
    actor: str = Field(sa_column=Column(String(255), nullable=False))
    from_status: str | None = Field(default=None, sa_column=Column(String(50), nullable=True))
    to_status: str | None = Field(default=None, sa_column=Column(String(50), nullable=True))
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class AllowedDomainTable(SQLModel, table=True):
    """Domains that outbound agent requests are allowed to target."""

    __tablename__ = "allowed_domains"

    id: str = Field(default_factory=_uuid_str, primary_key=True, index=True)
    domain: str = Field(sa_column=Column(String(255), nullable=False, unique=True))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConfidenceStatsTable(SQLModel, table=True):
    """Aggregated statistics used for adaptive CRAG thresholds."""

    __tablename__ = "confidence_stats"

    metric: str = Field(primary_key=True)
    sample_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    success_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    failure_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    rolling_score: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    rolling_threshold: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class UserTable(SQLModel, table=True):
    """Application user accounts with RBAC roles."""

    __tablename__ = "users"

    id: str = Field(default_factory=_uuid_str, primary_key=True, index=True)
    username: str = Field(sa_column=Column(String(150), nullable=False, unique=True))
    email: str | None = Field(default=None, sa_column=Column(String(255), nullable=True, unique=True))
    display_name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    hashed_password: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    roles: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
