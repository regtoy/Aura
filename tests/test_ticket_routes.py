from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import tickets
from app.dependencies.auth import User, get_current_user
from app.services.tickets import Ticket, TicketAggregate, TicketAuditLog, TicketMessage, TicketStatus


def build_ticket_aggregate() -> TicketAggregate:
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id="ticket-1",
        title="Kayıt sorunu",
        status=TicketStatus.NEW,
        priority="high",
        requester="editor",
        metadata={},
        created_at=now,
        updated_at=now,
    )
    message = TicketMessage(
        id="msg-1",
        ticket_id="ticket-1",
        author="editor",
        content="Merhaba",
        normalized_content="Merhaba",
        embedding=[1.0, 2.0],
        created_at=now,
    )
    audit = TicketAuditLog(
        id="audit-1",
        ticket_id="ticket-1",
        action="created",
        actor="editor",
        from_status=None,
        to_status=TicketStatus.NEW,
        metadata={},
        created_at=now,
    )
    return TicketAggregate(ticket=ticket, messages=[message], audit_logs=[audit])


class DummyTicketService:
    def __init__(self) -> None:
        self.aggregate = build_ticket_aggregate()

    async def list_tickets(self):
        return [self.aggregate.ticket]

    async def create_ticket(self, **kwargs):  # noqa: ANN003
        return self.aggregate

    async def get_ticket(self, ticket_id: str):
        return self.aggregate

    async def add_message(self, ticket_id: str, **kwargs):  # noqa: ANN003
        return self.aggregate

    async def change_status(self, ticket_id: str, **kwargs):  # noqa: ANN003
        return self.aggregate

    async def delete_ticket(self, ticket_id: str) -> None:
        return None


def test_ticket_routes_list_and_create():
    app = FastAPI()
    app.include_router(tickets.router)

    service = DummyTicketService()

    app.dependency_overrides[tickets.get_ticket_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: User("editor", roles=())

    client = TestClient(app)

    list_response = client.get("/tickets")
    assert list_response.status_code == 200
    items = list_response.json()
    assert items[0]["id"] == "ticket-1"

    create_response = client.post(
        "/tickets",
        json={"title": "Kayıt", "content": "Merhaba", "priority": "high", "metadata": {}},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["id"] == "ticket-1"
    assert payload["messages"][0]["embedding"] == [1.0, 2.0]
