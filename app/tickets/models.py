from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence
from uuid import UUID

from .state import TicketStatus


@dataclass(slots=True)
class Ticket:
    """Aggregate representing a support ticket entry."""

    id: UUID
    subject: str
    description: str
    normalized_description: str
    embedding: Sequence[float]
    status: TicketStatus
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class TicketAuditEntry:
    """History entry describing state or content changes for a ticket."""

    id: UUID
    ticket_id: UUID
    from_status: TicketStatus | None
    to_status: TicketStatus
    actor: str
    note: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)
