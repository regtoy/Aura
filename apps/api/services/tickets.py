from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

import asyncpg


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

    _CREATE_TICKETS_SQL = """
    CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        priority TEXT NOT NULL,
        requester TEXT NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """

    _CREATE_MESSAGES_SQL = """
    CREATE TABLE IF NOT EXISTS ticket_messages (
        id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
        author TEXT NOT NULL,
        content TEXT NOT NULL,
        normalized_content TEXT NOT NULL,
        embedding JSONB,
        created_at TIMESTAMPTZ NOT NULL
    )
    """

    _CREATE_AUDIT_SQL = """
    CREATE TABLE IF NOT EXISTS ticket_audit_logs (
        id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        actor TEXT NOT NULL,
        from_status TEXT,
        to_status TEXT,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL
    )
    """

    _INSERT_TICKET_SQL = """
    INSERT INTO tickets (id, title, status, priority, requester, metadata, created_at, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
    """

    _INSERT_MESSAGE_SQL = """
    INSERT INTO ticket_messages (id, ticket_id, author, content, normalized_content, embedding, created_at)
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
    """

    _INSERT_AUDIT_SQL = """
    INSERT INTO ticket_audit_logs (id, ticket_id, action, actor, from_status, to_status, metadata, created_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
    """

    _SELECT_TICKET_SQL = """
    SELECT id, title, status, priority, requester, metadata, created_at, updated_at
    FROM tickets
    WHERE id = $1
    """

    _SELECT_TICKETS_SQL = """
    SELECT id, title, status, priority, requester, metadata, created_at, updated_at
    FROM tickets
    ORDER BY created_at DESC
    """

    _SELECT_MESSAGES_SQL = """
    SELECT id, ticket_id, author, content, normalized_content, embedding, created_at
    FROM ticket_messages
    WHERE ticket_id = $1
    ORDER BY created_at ASC
    """

    _SELECT_AUDIT_LOGS_SQL = """
    SELECT id, ticket_id, action, actor, from_status, to_status, metadata, created_at
    FROM ticket_audit_logs
    WHERE ticket_id = $1
    ORDER BY created_at ASC
    """

    _UPDATE_STATUS_SQL = """
    UPDATE tickets
    SET status = $2, updated_at = $3
    WHERE id = $1
    RETURNING id, title, status, priority, requester, metadata, created_at, updated_at
    """

    _TOUCH_TICKET_SQL = """
    UPDATE tickets
    SET updated_at = $2
    WHERE id = $1
    RETURNING id, title, status, priority, requester, metadata, created_at, updated_at
    """

    _DELETE_TICKET_SQL = """
    DELETE FROM tickets WHERE id = $1 RETURNING id
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ensure_schema(self) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(self._CREATE_TICKETS_SQL)
            await connection.execute(self._CREATE_MESSAGES_SQL)
            await connection.execute(self._CREATE_AUDIT_SQL)

    async def create_ticket(
        self,
        ticket: Ticket,
        message: TicketMessage,
        audit: TicketAuditLog,
    ) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                self._INSERT_TICKET_SQL,
                ticket.id,
                ticket.title,
                ticket.status.value,
                ticket.priority,
                ticket.requester,
                dict(ticket.metadata),
                ticket.created_at,
                ticket.updated_at,
            )
            await connection.execute(
                self._INSERT_MESSAGE_SQL,
                message.id,
                message.ticket_id,
                message.author,
                message.content,
                message.normalized_content,
                list(message.embedding),
                message.created_at,
            )
            await connection.execute(
                self._INSERT_AUDIT_SQL,
                audit.id,
                audit.ticket_id,
                audit.action,
                audit.actor,
                audit.from_status.value if audit.from_status else None,
                audit.to_status.value if audit.to_status else None,
                dict(audit.metadata),
                audit.created_at,
            )

    async def add_message(self, message: TicketMessage) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                self._INSERT_MESSAGE_SQL,
                message.id,
                message.ticket_id,
                message.author,
                message.content,
                message.normalized_content,
                list(message.embedding),
                message.created_at,
            )

    async def add_audit_log(self, audit: TicketAuditLog) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                self._INSERT_AUDIT_SQL,
                audit.id,
                audit.ticket_id,
                audit.action,
                audit.actor,
                audit.from_status.value if audit.from_status else None,
                audit.to_status.value if audit.to_status else None,
                dict(audit.metadata),
                audit.created_at,
            )

    async def get_ticket(self, ticket_id: str) -> TicketAggregate | None:
        async with self._pool.acquire() as connection:
            ticket_row = await connection.fetchrow(self._SELECT_TICKET_SQL, ticket_id)
            if ticket_row is None:
                return None
            message_rows = await connection.fetch(self._SELECT_MESSAGES_SQL, ticket_id)
            audit_rows = await connection.fetch(self._SELECT_AUDIT_LOGS_SQL, ticket_id)

        ticket = self._row_to_ticket(ticket_row)
        messages = [self._row_to_message(row) for row in message_rows]
        audits = [self._row_to_audit(row) for row in audit_rows]
        return TicketAggregate(ticket=ticket, messages=messages, audit_logs=audits)

    async def list_tickets(self) -> Sequence[Ticket]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(self._SELECT_TICKETS_SQL)
        return [self._row_to_ticket(row) for row in rows]

    async def update_ticket_status(
        self, ticket_id: str, status: TicketStatus, updated_at: datetime
    ) -> Ticket | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(self._UPDATE_STATUS_SQL, ticket_id, status.value, updated_at)
        if row is None:
            return None
        return self._row_to_ticket(row)

    async def touch_ticket(self, ticket_id: str, updated_at: datetime) -> Ticket | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(self._TOUCH_TICKET_SQL, ticket_id, updated_at)
        if row is None:
            return None
        return self._row_to_ticket(row)

    async def delete_ticket(self, ticket_id: str) -> bool:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(self._DELETE_TICKET_SQL, ticket_id)
        return row is not None

    @staticmethod
    def _row_to_ticket(row: Mapping[str, Any]) -> Ticket:
        metadata = row.get("metadata") or {}
        status = TicketStatus(str(row["status"]))
        return Ticket(
            id=str(row["id"]),
            title=str(row["title"]),
            status=status,
            priority=str(row["priority"]),
            requester=str(row["requester"]),
            metadata=dict(metadata),
            created_at=_ensure_datetime(row["created_at"]),
            updated_at=_ensure_datetime(row["updated_at"]),
        )

    @staticmethod
    def _row_to_message(row: Mapping[str, Any]) -> TicketMessage:
        embedding = row.get("embedding") or []
        return TicketMessage(
            id=str(row["id"]),
            ticket_id=str(row["ticket_id"]),
            author=str(row["author"]),
            content=str(row["content"]),
            normalized_content=str(row["normalized_content"]),
            embedding=[float(value) for value in embedding],
            created_at=_ensure_datetime(row["created_at"]),
        )

    @staticmethod
    def _row_to_audit(row: Mapping[str, Any]) -> TicketAuditLog:
        metadata = row.get("metadata") or {}
        from_status = row.get("from_status")
        to_status = row.get("to_status")
        return TicketAuditLog(
            id=str(row["id"]),
            ticket_id=str(row["ticket_id"]),
            action=str(row["action"]),
            actor=str(row["actor"]),
            from_status=TicketStatus(str(from_status)) if from_status else None,
            to_status=TicketStatus(str(to_status)) if to_status else None,
            metadata=dict(metadata),
            created_at=_ensure_datetime(row["created_at"]),
        )


def _ensure_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.fromisoformat(str(value))


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
