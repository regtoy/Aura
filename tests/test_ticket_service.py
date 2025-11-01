from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.tickets import (
    DefaultTicketEmbedder,
    Ticket,
    TicketAggregate,
    TicketProcessingPipeline,
    TicketService,
    TicketStateMachine,
    TicketStatus,
)


class DummyRepository:
    def __init__(self):
        self.create_ticket = AsyncMock()
        self.add_message = AsyncMock()
        self.add_audit_log = AsyncMock()
        self.touch_ticket = AsyncMock(return_value=None)
        self.update_ticket_status = AsyncMock()
        self.delete_ticket = AsyncMock(return_value=True)
        self.list_tickets = AsyncMock(return_value=[])
        self.get_ticket = AsyncMock()


@pytest.mark.asyncio
async def test_pipeline_normalizes_and_embeds():
    class StubEmbedder(DefaultTicketEmbedder):
        async def embed(self, text: str):  # type: ignore[override]
            return [float(len(text)), 1.0]

    pipeline = TicketProcessingPipeline(embedder=StubEmbedder())
    result = await pipeline.process("  Hello\nWorld   ")
    assert result.normalized == "Hello World"
    assert result.embedding == [11.0, 1.0]


def test_state_machine_validates_transitions():
    machine = TicketStateMachine()
    assert machine.can_transition(TicketStatus.NEW, TicketStatus.TRIAGED)
    with pytest.raises(ValueError):
        machine.assert_transition(TicketStatus.NEW, TicketStatus.RESOLVED)


@pytest.mark.asyncio
async def test_ticket_creation_records_audit_and_message():
    repository = DummyRepository()
    service = TicketService(repository, pipeline=TicketProcessingPipeline())

    aggregate = await service.create_ticket(
        title="Kayıt sorunu",
        content="Öğrenci kaydı yapılamıyor",
        requester="editor",
        priority="high",
        metadata={"campus": "istanbul"},
    )

    repository.create_ticket.assert_awaited()
    assert aggregate.ticket.title == "Kayıt sorunu"
    assert aggregate.ticket.status == TicketStatus.NEW
    assert aggregate.messages[0].normalized_content.startswith("Öğrenci")
    assert aggregate.audit_logs[0].action == "created"


@pytest.mark.asyncio
async def test_change_status_uses_state_machine():
    repository = DummyRepository()
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id="t-1",
        title="Test",
        status=TicketStatus.NEW,
        priority="medium",
        requester="viewer",
        metadata={},
        created_at=now,
        updated_at=now,
    )
    aggregate = TicketAggregate(ticket=ticket, messages=[], audit_logs=[])
    repository.get_ticket.return_value = aggregate
    repository.update_ticket_status.return_value = ticket

    service = TicketService(repository, state_machine=TicketStateMachine())

    with pytest.raises(ValueError):
        await service.change_status("t-1", new_status=TicketStatus.RESOLVED, actor="editor")

    await service.change_status("t-1", new_status=TicketStatus.TRIAGED, actor="editor")
    repository.update_ticket_status.assert_awaited()
    repository.add_audit_log.assert_awaited()
