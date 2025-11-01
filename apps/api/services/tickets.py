from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel, select

from packages.db.models import TicketAuditLogTable, TicketMessageTable, TicketTable


class TicketNotFoundError(RuntimeError):
    """Raised when an operation targets a non-existent ticket."""


class TicketStatus(str, Enum):
    """Canonical states of the ticket lifecycle."""

    NEW = "new"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass(slots=True)
class Ticket:
    """Primary ticket record."""

    id: str
    title: str
    status: TicketStatus
    priority: str
    requester: str
    metadata: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class TicketMessage:
    """Individual message belonging to a ticket."""

    id: str
    ticket_id: str
    author: str
    content: str
    normalized_content: str
    embedding: Sequence[float]
    created_at: datetime


@dataclass(slots=True)
class TicketAuditLog:
    """Audit information describing discrete ticket actions."""

    id: str
    ticket_id: str
    action: str
    actor: str
    from_status: TicketStatus | None
    to_status: TicketStatus | None
    metadata: Mapping[str, Any]
    created_at: datetime


@dataclass(slots=True)
class TicketAggregate:
    """Container bundling the ticket with messages and audit logs."""

    ticket: Ticket
    messages: Sequence[TicketMessage]
    audit_logs: Sequence[TicketAuditLog]


class TicketStateMachine:
    """Validate ticket status transitions."""

    _DEFAULT_TRANSITIONS: Mapping[TicketStatus, Sequence[TicketStatus]] = {
        TicketStatus.NEW: (TicketStatus.TRIAGED, TicketStatus.CLOSED),
        TicketStatus.TRIAGED: (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED),
        TicketStatus.IN_PROGRESS: (TicketStatus.RESOLVED, TicketStatus.CLOSED),
        TicketStatus.RESOLVED: (TicketStatus.CLOSED, TicketStatus.IN_PROGRESS),
        TicketStatus.CLOSED: (),
    }

    def __init__(self, transitions: Mapping[TicketStatus, Sequence[TicketStatus]] | None = None) -> None:
        self._transitions = transitions or self._DEFAULT_TRANSITIONS

    def can_transition(self, current: TicketStatus, target: TicketStatus) -> bool:
        allowed = self._transitions.get(current, ())
        return target in allowed

    def assert_transition(self, current: TicketStatus, target: TicketStatus) -> None:
        if current == target:
            return
        if not self.can_transition(current, target):
            raise ValueError(f"Invalid status transition: {current!s} -> {target!s}")


class TicketNormalizer:
    """Utility responsible for text cleanup prior to embedding."""

    def normalize(self, text: str) -> str:
        collapsed = " ".join(text.split())
        return collapsed.strip()


class TicketEmbedder(Protocol):
    async def embed(self, text: str) -> Sequence[float]:
        ...


class DefaultTicketEmbedder:
    """Deterministic embedding fallback that does not require optional deps."""

    def __init__(self, *, vector_size: int = 8) -> None:
        self._vector_size = max(3, vector_size)

    async def embed(self, text: str) -> Sequence[float]:  # pragma: no cover - thin wrapper
        return self._fallback_vector(text)

    def _fallback_vector(self, text: str) -> list[float]:
        cleaned = text.encode("utf-8", errors="ignore")
        length = float(len(cleaned))
        word_count = float(len(text.split()))
        checksum = sum(cleaned) % 997
        seed = float(checksum) / 997.0
        vector: list[float] = [length, word_count, seed]
        while len(vector) < self._vector_size:
            seed = math.fmod((seed * 1.61803398875) + 0.13579, 1.0)
            vector.append(seed)
        return vector


@dataclass(slots=True)
class TicketProcessingResult:
    """Structured output of the normalization & embedding pipeline."""

    original: str
    normalized: str
    embedding: Sequence[float]


class TicketProcessingPipeline:
    """Pipeline executing normalization and embedding for ticket content."""

    def __init__(
        self,
        *,
        normalizer: TicketNormalizer | None = None,
        embedder: TicketEmbedder | None = None,
    ) -> None:
        self._normalizer = normalizer or TicketNormalizer()
        self._embedder = embedder or DefaultTicketEmbedder()

    async def process(self, text: str) -> TicketProcessingResult:
        normalized = self._normalizer.normalize(text)
        embedding = await self._embedder.embed(normalized)
        return TicketProcessingResult(original=text, normalized=normalized, embedding=list(map(float, embedding)))


class TicketRepository:
    """Persistence helper wrapping `tickets`, `ticket_messages` and audit logs."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        engine: AsyncEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._engine: AsyncEngine | None = engine

    async def ensure_schema(self) -> None:
        if self._engine is None:
            raise RuntimeError("Session factory is not bound to an async engine")
        async with self._engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    async def create_ticket(
        self,
        ticket: Ticket,
        message: TicketMessage,
        audit: TicketAuditLog,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    TicketTable(
                        id=ticket.id,
                        title=ticket.title,
                        status=ticket.status.value,
                        priority=ticket.priority,
                        requester=ticket.requester,
                        metadata_=dict(ticket.metadata),
                        created_at=ticket.created_at,
                        updated_at=ticket.updated_at,
                    )
                )
                session.add(
                    TicketMessageTable(
                        id=message.id,
                        ticket_id=message.ticket_id,
                        author=message.author,
                        content=message.content,
                        normalized_content=message.normalized_content,
                        embedding=list(message.embedding),
                        created_at=message.created_at,
                    )
                )
                session.add(
                    TicketAuditLogTable(
                        id=audit.id,
                        ticket_id=audit.ticket_id,
                        action=audit.action,
                        actor=audit.actor,
                        from_status=audit.from_status.value if audit.from_status else None,
                        to_status=audit.to_status.value if audit.to_status else None,
                        metadata_=dict(audit.metadata),
                        created_at=audit.created_at,
                    )
                )

    async def add_message(self, message: TicketMessage) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    TicketMessageTable(
                        id=message.id,
                        ticket_id=message.ticket_id,
                        author=message.author,
                        content=message.content,
                        normalized_content=message.normalized_content,
                        embedding=list(message.embedding),
                        created_at=message.created_at,
                    )
                )

    async def add_audit_log(self, audit: TicketAuditLog) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    TicketAuditLogTable(
                        id=audit.id,
                        ticket_id=audit.ticket_id,
                        action=audit.action,
                        actor=audit.actor,
                        from_status=audit.from_status.value if audit.from_status else None,
                        to_status=audit.to_status.value if audit.to_status else None,
                        metadata_=dict(audit.metadata),
                        created_at=audit.created_at,
                    )
                )

    async def get_ticket(self, ticket_id: str) -> TicketAggregate | None:
        async with self._session_factory() as session:
            ticket_row = await session.get(TicketTable, ticket_id)
            if ticket_row is None:
                return None

            message_result = await session.execute(
                select(TicketMessageTable)
                .where(TicketMessageTable.ticket_id == ticket_id)
                .order_by(TicketMessageTable.created_at.asc())
            )
            audit_result = await session.execute(
                select(TicketAuditLogTable)
                .where(TicketAuditLogTable.ticket_id == ticket_id)
                .order_by(TicketAuditLogTable.created_at.asc())
            )

        ticket = self._table_to_ticket(ticket_row)
        messages = [self._table_to_message(row) for row in message_result.scalars().all()]
        audits = [self._table_to_audit(row) for row in audit_result.scalars().all()]
        return TicketAggregate(ticket=ticket, messages=messages, audit_logs=audits)

    async def list_tickets(self) -> Sequence[Ticket]:
        async with self._session_factory() as session:
            result = await session.execute(select(TicketTable).order_by(TicketTable.created_at.desc()))
            return [self._table_to_ticket(row) for row in result.scalars().all()]

    async def update_ticket_status(
        self, ticket_id: str, status: TicketStatus, updated_at: datetime
    ) -> Ticket | None:
        async with self._session_factory() as session:
            ticket_row = await session.get(TicketTable, ticket_id)
            if ticket_row is None:
                return None
            ticket_row.status = status.value
            ticket_row.updated_at = updated_at
            await session.commit()
            await session.refresh(ticket_row)
            return self._table_to_ticket(ticket_row)

    async def touch_ticket(self, ticket_id: str, updated_at: datetime) -> Ticket | None:
        async with self._session_factory() as session:
            ticket_row = await session.get(TicketTable, ticket_id)
            if ticket_row is None:
                return None
            ticket_row.updated_at = updated_at
            await session.commit()
            await session.refresh(ticket_row)
            return self._table_to_ticket(ticket_row)

    async def delete_ticket(self, ticket_id: str) -> bool:
        async with self._session_factory() as session:
            ticket_row = await session.get(TicketTable, ticket_id)
            if ticket_row is None:
                return False
            await session.delete(ticket_row)
            await session.commit()
            return True

    @staticmethod
    def _table_to_ticket(row: TicketTable) -> Ticket:
        return Ticket(
            id=row.id,
            title=row.title,
            status=TicketStatus(row.status),
            priority=row.priority,
            requester=row.requester,
            metadata=dict(row.metadata_ or {}),
            created_at=_ensure_datetime(row.created_at),
            updated_at=_ensure_datetime(row.updated_at),
        )

    @staticmethod
    def _table_to_message(row: TicketMessageTable) -> TicketMessage:
        embedding = row.embedding or []
        return TicketMessage(
            id=row.id,
            ticket_id=row.ticket_id,
            author=row.author,
            content=row.content,
            normalized_content=row.normalized_content,
            embedding=[float(value) for value in embedding],
            created_at=_ensure_datetime(row.created_at),
        )

    @staticmethod
    def _table_to_audit(row: TicketAuditLogTable) -> TicketAuditLog:
        from_status = row.from_status
        to_status = row.to_status
        return TicketAuditLog(
            id=row.id,
            ticket_id=row.ticket_id,
            action=row.action,
            actor=row.actor,
            from_status=TicketStatus(from_status) if from_status else None,
            to_status=TicketStatus(to_status) if to_status else None,
            metadata=dict(row.metadata_ or {}),
            created_at=_ensure_datetime(row.created_at),
        )


def _ensure_datetime(value: datetime | None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    raise TypeError("Expected datetime value from database")
class TicketService:
    """High level orchestration for ticket CRUD, state machine and audit logging."""

    def __init__(
        self,
        repository: TicketRepository,
        *,
        pipeline: TicketProcessingPipeline | None = None,
        state_machine: TicketStateMachine | None = None,
    ) -> None:
        self._repository = repository
        self._pipeline = pipeline or TicketProcessingPipeline()
        self._state_machine = state_machine or TicketStateMachine()

    async def create_ticket(
        self,
        *,
        title: str,
        content: str,
        requester: str,
        priority: str = "medium",
        metadata: Mapping[str, Any] | None = None,
    ) -> TicketAggregate:
        now = datetime.now(timezone.utc)
        ticket_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        audit_id = str(uuid.uuid4())

        processed = await self._pipeline.process(content)

        ticket = Ticket(
            id=ticket_id,
            title=title,
            status=TicketStatus.NEW,
            priority=priority,
            requester=requester,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        message = TicketMessage(
            id=message_id,
            ticket_id=ticket_id,
            author=requester,
            content=processed.original,
            normalized_content=processed.normalized,
            embedding=list(processed.embedding),
            created_at=now,
        )
        audit = TicketAuditLog(
            id=audit_id,
            ticket_id=ticket_id,
            action="created",
            actor=requester,
            from_status=None,
            to_status=TicketStatus.NEW,
            metadata=dict(metadata or {}),
            created_at=now,
        )

        await self._repository.create_ticket(ticket, message, audit)
        return TicketAggregate(ticket=ticket, messages=[message], audit_logs=[audit])

    async def list_tickets(self) -> Sequence[Ticket]:
        return await self._repository.list_tickets()

    async def get_ticket(self, ticket_id: str) -> TicketAggregate:
        aggregate = await self._repository.get_ticket(ticket_id)
        if aggregate is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")
        return aggregate

    async def delete_ticket(self, ticket_id: str) -> None:
        deleted = await self._repository.delete_ticket(ticket_id)
        if not deleted:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")

    async def add_message(self, ticket_id: str, *, content: str, author: str) -> TicketAggregate:
        aggregate = await self._repository.get_ticket(ticket_id)
        if aggregate is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")

        processed = await self._pipeline.process(content)
        now = datetime.now(timezone.utc)

        message = TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            author=author,
            content=processed.original,
            normalized_content=processed.normalized,
            embedding=list(processed.embedding),
            created_at=now,
        )
        await self._repository.add_message(message)

        audit = TicketAuditLog(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            action="message_added",
            actor=author,
            from_status=aggregate.ticket.status,
            to_status=aggregate.ticket.status,
            metadata={},
            created_at=now,
        )
        await self._repository.add_audit_log(audit)
        updated_ticket = await self._repository.touch_ticket(ticket_id, now)
        ticket = updated_ticket or replace(aggregate.ticket, updated_at=now)

        return TicketAggregate(
            ticket=ticket,
            messages=[*aggregate.messages, message],
            audit_logs=[*aggregate.audit_logs, audit],
        )

    async def change_status(
        self,
        ticket_id: str,
        *,
        new_status: TicketStatus,
        actor: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> TicketAggregate:
        aggregate = await self._repository.get_ticket(ticket_id)
        if aggregate is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")

        current = aggregate.ticket.status
        self._state_machine.assert_transition(current, new_status)

        now = datetime.now(timezone.utc)
        updated_ticket = await self._repository.update_ticket_status(ticket_id, new_status, now)
        if updated_ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")

        audit = TicketAuditLog(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            action="status_changed",
            actor=actor,
            from_status=current,
            to_status=new_status,
            metadata=dict(metadata or {}),
            created_at=now,
        )
        await self._repository.add_audit_log(audit)

        return TicketAggregate(
            ticket=updated_ticket,
            messages=list(aggregate.messages),
            audit_logs=[*aggregate.audit_logs, audit],
        )
