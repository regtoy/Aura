from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID, uuid4

import asyncpg

from .models import Ticket, TicketAuditEntry
from .state import TicketStatus


class TicketRepository:
    """Data access layer for ticket records."""

    _CREATE_TICKETS_SQL = """
    CREATE TABLE IF NOT EXISTS tickets (
        id UUID PRIMARY KEY,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        normalized_description TEXT NOT NULL,
        embedding DOUBLE PRECISION[] NOT NULL,
        status TEXT NOT NULL,
        created_by TEXT NOT NULL,
        updated_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """

    _CREATE_AUDIT_SQL = """
    CREATE TABLE IF NOT EXISTS ticket_audit_logs (
        id UUID PRIMARY KEY,
        ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
        from_status TEXT NULL,
        to_status TEXT NOT NULL,
        actor TEXT NOT NULL,
        note TEXT NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """

    _INSERT_TICKET_SQL = """
    INSERT INTO tickets (id, subject, description, normalized_description, embedding, status, created_by, updated_by)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
    RETURNING id, subject, description, normalized_description, embedding, status, created_by, updated_by, created_at, updated_at
    """

    _UPDATE_TICKET_SQL = """
    UPDATE tickets
    SET subject = $2,
        description = $3,
        normalized_description = $4,
        embedding = $5,
        updated_by = $6,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = $1
    RETURNING id, subject, description, normalized_description, embedding, status, created_by, updated_by, created_at, updated_at
    """

    _SELECT_TICKET_SQL = """
    SELECT id, subject, description, normalized_description, embedding, status, created_by, updated_by, created_at, updated_at
    FROM tickets
    WHERE id = $1
    """

    _LIST_TICKETS_SQL = """
    SELECT id, subject, description, normalized_description, embedding, status, created_by, updated_by, created_at, updated_at
    FROM tickets
    ORDER BY created_at DESC
    """

    _LIST_TICKETS_BY_STATUS_SQL = """
    SELECT id, subject, description, normalized_description, embedding, status, created_by, updated_by, created_at, updated_at
    FROM tickets
    WHERE status = $1
    ORDER BY created_at DESC
    """

    _DELETE_TICKET_SQL = """
    DELETE FROM tickets WHERE id = $1
    """

    _UPDATE_STATUS_SQL = """
    UPDATE tickets
    SET status = $2,
        updated_by = $3,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = $1
    RETURNING id, subject, description, normalized_description, embedding, status, created_by, updated_by, created_at, updated_at
    """

    _INSERT_AUDIT_SQL = """
    INSERT INTO ticket_audit_logs (id, ticket_id, from_status, to_status, actor, note, metadata)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    """

    _SELECT_AUDIT_SQL = """
    SELECT id, ticket_id, from_status, to_status, actor, note, metadata, created_at
    FROM ticket_audit_logs
    WHERE ticket_id = $1
    ORDER BY created_at ASC
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ensure_schema(self) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(self._CREATE_TICKETS_SQL)
            await connection.execute(self._CREATE_AUDIT_SQL)

    async def create_ticket(
        self,
        *,
        ticket_id: UUID,
        subject: str,
        description: str,
        normalized_description: str,
        embedding: Sequence[float],
        status: TicketStatus,
        created_by: str,
        note: str = "Ticket created",
    ) -> Ticket:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                self._INSERT_TICKET_SQL,
                ticket_id,
                subject,
                description,
                normalized_description,
                list(embedding),
                status.value,
                created_by,
            )
            if row is None:
                raise RuntimeError("Failed to insert ticket")
            await self._insert_audit(
                connection,
                ticket_id=ticket_id,
                from_status=None,
                to_status=status,
                actor=created_by,
                note=note,
                metadata={},
            )
            return self._row_to_ticket(row)

    async def update_ticket(
        self,
        *,
        ticket_id: UUID,
        subject: str,
        description: str,
        normalized_description: str,
        embedding: Sequence[float],
        updated_by: str,
        note: str = "Ticket updated",
    ) -> Ticket | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                self._UPDATE_TICKET_SQL,
                ticket_id,
                subject,
                description,
                normalized_description,
                list(embedding),
                updated_by,
            )
            if row is None:
                return None
            await self._insert_audit(
                connection,
                ticket_id=ticket_id,
                from_status=TicketStatus(str(row["status"])),
                to_status=TicketStatus(str(row["status"])),
                actor=updated_by,
                note=note,
                metadata={},
            )
            return self._row_to_ticket(row)

    async def get_ticket(self, ticket_id: UUID) -> Ticket | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(self._SELECT_TICKET_SQL, ticket_id)
            if row is None:
                return None
            return self._row_to_ticket(row)

    async def list_tickets(self, *, status: TicketStatus | None = None) -> list[Ticket]:
        async with self._pool.acquire() as connection:
            if status is None:
                rows = await connection.fetch(self._LIST_TICKETS_SQL)
            else:
                rows = await connection.fetch(self._LIST_TICKETS_BY_STATUS_SQL, status.value)
            return [self._row_to_ticket(row) for row in rows]

    async def delete_ticket(self, ticket_id: UUID) -> bool:
        async with self._pool.acquire() as connection:
            result = await connection.execute(self._DELETE_TICKET_SQL, ticket_id)
        if isinstance(result, str):
            return result.strip().endswith("1")
        return bool(result)

    async def change_status(
        self,
        *,
        ticket_id: UUID,
        from_status: TicketStatus,
        to_status: TicketStatus,
        actor: str,
        note: str = "Status updated",
        metadata: dict[str, Any] | None = None,
    ) -> Ticket | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                self._UPDATE_STATUS_SQL,
                ticket_id,
                to_status.value,
                actor,
            )
            if row is None:
                return None
            await self._insert_audit(
                connection,
                ticket_id=ticket_id,
                from_status=from_status,
                to_status=to_status,
                actor=actor,
                note=note,
                metadata=metadata or {},
            )
            return self._row_to_ticket(row)

    async def get_audit_log(self, ticket_id: UUID) -> list[TicketAuditEntry]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(self._SELECT_AUDIT_SQL, ticket_id)
            return [self._row_to_audit(row) for row in rows]

    async def _insert_audit(
        self,
        connection: Any,
        *,
        ticket_id: UUID,
        from_status: TicketStatus | None,
        to_status: TicketStatus,
        actor: str,
        note: str,
        metadata: dict[str, Any],
    ) -> None:
        await connection.execute(
            self._INSERT_AUDIT_SQL,
            uuid4(),
            ticket_id,
            None if from_status is None else from_status.value,
            to_status.value,
            actor,
            note,
            metadata,
        )

    @staticmethod
    def _row_to_ticket(row: Any) -> Ticket:
        return Ticket(
            id=_to_uuid(row["id"]),
            subject=str(row["subject"]),
            description=str(row["description"]),
            normalized_description=str(row["normalized_description"]),
            embedding=list(row["embedding"]),
            status=TicketStatus(str(row["status"])),
            created_by=str(row["created_by"]),
            updated_by=str(row["updated_by"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_audit(row: Any) -> TicketAuditEntry:
        from_status = row["from_status"]
        metadata = row["metadata"] if row["metadata"] is not None else {}
        return TicketAuditEntry(
            id=_to_uuid(row["id"]),
            ticket_id=_to_uuid(row["ticket_id"]),
            from_status=TicketStatus(str(from_status)) if from_status else None,
            to_status=TicketStatus(str(row["to_status"])),
            actor=str(row["actor"]),
            note=str(row["note"]),
            metadata=dict(metadata),
            created_at=row["created_at"],
        )


def _to_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
