from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.tickets.repository import TicketRepository
from app.tickets.state import TicketStatus


class DummyAcquire:
    def __init__(self, connection):
        self._connection = connection

    async def __aenter__(self):
        return self._connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyPool:
    def __init__(self, connection):
        self._connection = connection

    def acquire(self):
        return DummyAcquire(self._connection)


@pytest.mark.asyncio
async def test_create_ticket_inserts_and_logs_audit():
    ticket_id = uuid4()
    now = datetime.now(timezone.utc)
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(
        return_value={
            "id": ticket_id,
            "subject": "Subject",
            "description": "Body",
            "normalized_description": "body",
            "embedding": [0.1, 0.2],
            "status": TicketStatus.NEW.value,
            "created_by": "alice",
            "updated_by": "alice",
            "created_at": now,
            "updated_at": now,
        }
    )
    pool = DummyPool(connection)
    repo = TicketRepository(pool)

    ticket = await repo.create_ticket(
        ticket_id=ticket_id,
        subject="Subject",
        description="Body",
        normalized_description="body",
        embedding=[0.1, 0.2],
        status=TicketStatus.NEW,
        created_by="alice",
    )

    assert ticket.id == ticket_id
    assert ticket.status is TicketStatus.NEW
    connection.fetchrow.assert_awaited()
    connection.execute.assert_awaited()


@pytest.mark.asyncio
async def test_change_status_updates_ticket_and_appends_audit():
    ticket_id = uuid4()
    now = datetime.now(timezone.utc)
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(
        return_value={
            "id": ticket_id,
            "subject": "Subject",
            "description": "Body",
            "normalized_description": "body",
            "embedding": [0.1, 0.2],
            "status": TicketStatus.RESOLVED.value,
            "created_by": "alice",
            "updated_by": "bob",
            "created_at": now,
            "updated_at": now,
        }
    )
    pool = DummyPool(connection)
    repo = TicketRepository(pool)

    ticket = await repo.change_status(
        ticket_id=ticket_id,
        from_status=TicketStatus.IN_PROGRESS,
        to_status=TicketStatus.RESOLVED,
        actor="bob",
    )

    assert ticket is not None
    assert ticket.status is TicketStatus.RESOLVED
    assert connection.fetchrow.await_args[0][0] == repo._UPDATE_STATUS_SQL
    assert connection.execute.await_count >= 1
