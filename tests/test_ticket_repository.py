from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from apps.api.services.tickets import (
    Ticket,
    TicketAggregate,
    TicketAuditLog,
    TicketMessage,
    TicketRepository,
    TicketStatus,
)


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_ensure_schema_creates_tables(engine: AsyncEngine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = TicketRepository(factory, engine=engine)

    await repo.ensure_schema()

    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda sync_conn: set(sa_inspect(sync_conn).get_table_names()))

    assert {"tickets", "ticket_messages", "ticket_audit_logs"}.issubset(tables)


@pytest.mark.asyncio
async def test_update_ticket_status_returns_ticket(
    session_factory: async_sessionmaker, engine: AsyncEngine
):
    repo = TicketRepository(session_factory, engine=engine)

    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id="ticket-1",
        title="Deneme",
        status=TicketStatus.NEW,
        priority="medium",
        requester="editor",
        metadata={"foo": "bar"},
        created_at=now,
        updated_at=now,
    )
    message = TicketMessage(
        id="msg-1",
        ticket_id=ticket.id,
        author="editor",
        content="Merhaba",
        normalized_content="Merhaba",
        embedding=[1.0, 2.0],
        created_at=now,
    )
    audit = TicketAuditLog(
        id="audit-1",
        ticket_id=ticket.id,
        action="created",
        actor="editor",
        from_status=None,
        to_status=TicketStatus.NEW,
        metadata={},
        created_at=now,
    )

    await repo.create_ticket(ticket, message, audit)

    updated_time = datetime.now(timezone.utc)
    updated = await repo.update_ticket_status(ticket.id, TicketStatus.TRIAGED, updated_time)

    assert isinstance(updated, Ticket)
    assert updated.status == TicketStatus.TRIAGED
    assert updated.updated_at == updated_time


@pytest.mark.asyncio
async def test_get_ticket_aggregates_rows(
    session_factory: async_sessionmaker, engine: AsyncEngine
):
    repo = TicketRepository(session_factory, engine=engine)

    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id="ticket-1",
        title="Deneme",
        status=TicketStatus.NEW,
        priority="medium",
        requester="editor",
        metadata={},
        created_at=now,
        updated_at=now,
    )
    message = TicketMessage(
        id="msg-1",
        ticket_id=ticket.id,
        author="editor",
        content="Merhaba",
        normalized_content="Merhaba",
        embedding=[1.0, 2.0],
        created_at=now,
    )
    audit = TicketAuditLog(
        id="audit-1",
        ticket_id=ticket.id,
        action="created",
        actor="editor",
        from_status=None,
        to_status=TicketStatus.NEW,
        metadata={},
        created_at=now,
    )

    await repo.create_ticket(ticket, message, audit)

    aggregate = await repo.get_ticket(ticket.id)

    assert isinstance(aggregate, TicketAggregate)
    assert aggregate.ticket.id == ticket.id
    assert aggregate.messages[0].id == message.id
    assert aggregate.audit_logs[0].action == "created"
