from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.tickets.models import Ticket
from app.tickets.pipeline import TicketEmbeddingResult
from app.tickets.service import InvalidTicketTransitionError, TicketNotFoundError, TicketService
from app.tickets.state import TicketStatus


class DummyPipeline:
    def __init__(self):
        self.run_calls: list[str] = []
        self.batch_calls: list[list[str]] = []

    def run(self, text: str) -> TicketEmbeddingResult:
        self.run_calls.append(text)
        return TicketEmbeddingResult(normalized_text=text.lower(), embedding=[0.1])

    def encode_batch(self, texts: list[str]) -> list[TicketEmbeddingResult]:
        self.batch_calls.append(texts)
        return [TicketEmbeddingResult(normalized_text=text.lower(), embedding=[0.1]) for text in texts]


@pytest.mark.asyncio
async def test_change_status_validates_transitions():
    ticket_id = uuid4()
    repository = AsyncMock()
    repository.get_ticket = AsyncMock(
        return_value=Ticket(
            id=ticket_id,
            subject="Subject",
            description="Body",
            normalized_description="body",
            embedding=[0.1],
            status=TicketStatus.CLOSED,
            created_by="alice",
            updated_by="alice",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    service = TicketService(repository=repository, pipeline=DummyPipeline())

    with pytest.raises(InvalidTicketTransitionError):
        await service.change_status(ticket_id, new_status=TicketStatus.TRIAGED, actor="bob")


@pytest.mark.asyncio
async def test_update_ticket_uses_pipeline_when_description_changes():
    ticket_id = uuid4()
    now = datetime.now(timezone.utc)
    pipeline = DummyPipeline()
    repository = AsyncMock()
    repository.get_ticket = AsyncMock(
        return_value=Ticket(
            id=ticket_id,
            subject="Subject",
            description="Body",
            normalized_description="body",
            embedding=[0.1],
            status=TicketStatus.NEW,
            created_by="alice",
            updated_by="alice",
            created_at=now,
            updated_at=now,
        )
    )
    repository.update_ticket = AsyncMock(return_value=repository.get_ticket.return_value)

    service = TicketService(repository=repository, pipeline=pipeline)

    await service.update_ticket(ticket_id, description="Updated", actor="alice")

    assert pipeline.run_calls == ["Updated"]
    assert pipeline.batch_calls == []


@pytest.mark.asyncio
async def test_delete_ticket_raises_when_missing():
    repository = AsyncMock()
    repository.delete_ticket = AsyncMock(return_value=False)
    service = TicketService(repository=repository, pipeline=DummyPipeline())

    with pytest.raises(TicketNotFoundError):
        await service.delete_ticket(uuid4())
