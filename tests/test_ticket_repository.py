from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from apps.api.services.tickets import TicketRepository, TicketStatus


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
async def test_ensure_schema_creates_tables():
    connection = AsyncMock()
    pool = DummyPool(connection)
    repository = TicketRepository(pool)

    await repository.ensure_schema()

    assert connection.execute.await_count == 3
    executed = [call.args[0] for call in connection.execute.await_args_list]
    assert any("CREATE TABLE IF NOT EXISTS tickets" in stmt for stmt in executed)
    assert any("ticket_messages" in stmt for stmt in executed)
    assert any("ticket_audit_logs" in stmt for stmt in executed)


@pytest.mark.asyncio
async def test_update_ticket_status_returns_ticket():
    now = datetime.now(timezone.utc)
    row = {
        "id": "ticket-1",
        "title": "Deneme",
        "status": "triaged",
        "priority": "medium",
        "requester": "editor",
        "metadata": {"foo": "bar"},
        "created_at": now,
        "updated_at": now,
    }
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(return_value=row)
    pool = DummyPool(connection)
    repository = TicketRepository(pool)

    updated = await repository.update_ticket_status("ticket-1", TicketStatus.TRIAGED, now)

    assert updated is not None
    assert updated.status == TicketStatus.TRIAGED
    connection.fetchrow.assert_awaited()


@pytest.mark.asyncio
async def test_get_ticket_aggregates_rows():
    now = datetime.now(timezone.utc)
    ticket_row = {
        "id": "ticket-1",
        "title": "Deneme",
        "status": "new",
        "priority": "medium",
        "requester": "editor",
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    message_row = {
        "id": "msg-1",
        "ticket_id": "ticket-1",
        "author": "editor",
        "content": "Merhaba",
        "normalized_content": "Merhaba",
        "embedding": [1.0, 2.0],
        "created_at": now,
    }
    audit_row = {
        "id": "audit-1",
        "ticket_id": "ticket-1",
        "action": "created",
        "actor": "editor",
        "from_status": None,
        "to_status": "new",
        "metadata": {},
        "created_at": now,
    }

    connection = AsyncMock()
    connection.fetchrow = AsyncMock(side_effect=[ticket_row])
    connection.fetch = AsyncMock(side_effect=[[message_row], [audit_row]])
    pool = DummyPool(connection)
    repository = TicketRepository(pool)

    aggregate = await repository.get_ticket("ticket-1")
    assert aggregate is not None
    assert aggregate.ticket.id == "ticket-1"
    assert aggregate.messages[0].id == "msg-1"
    assert aggregate.audit_logs[0].action == "created"
