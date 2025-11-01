from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
import pytest

from app.api.routes import tickets as ticket_routes
from app.dependencies import tickets as ticket_deps
from app.dependencies.auth import Role, User
from app.main import create_app
from app.tickets.models import Ticket, TicketAuditEntry
from app.tickets.service import InvalidTicketTransitionError
from app.tickets.state import TicketStatus


def _make_ticket(*, status: TicketStatus = TicketStatus.NEW) -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        id=uuid4(),
        subject="Subject",
        description="Body",
        normalized_description="body",
        embedding=[0.1, 0.2],
        status=status,
        created_by="editor",
        updated_by="editor",
        created_at=now,
        updated_at=now,
    )


def _make_audit(ticket_id, *, to_status: TicketStatus = TicketStatus.NEW) -> TicketAuditEntry:
    return TicketAuditEntry(
        id=uuid4(),
        ticket_id=ticket_id,
        from_status=None,
        to_status=to_status,
        actor="editor",
        note="created",
        metadata={},
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def ticket_client():
    app = create_app()
    service = AsyncMock()

    user_editor = User("editor", (Role.EDITOR, Role.VIEWER))
    user_viewer = User("viewer", (Role.VIEWER,))

    async def override_service():
        return service

    app.dependency_overrides[ticket_routes.get_ticket_service] = override_service
    app.dependency_overrides[ticket_deps.require_editor] = lambda: user_editor
    app.dependency_overrides[ticket_deps.require_viewer] = lambda: user_viewer

    client = TestClient(app)
    try:
        yield client, service
    finally:
        app.dependency_overrides.clear()


def test_create_ticket_endpoint_returns_created(ticket_client):
    client, service = ticket_client
    ticket = _make_ticket()
    service.create_ticket = AsyncMock(return_value=ticket)

    response = client.post("/tickets", json={"subject": "Subject", "description": "Body"})

    assert response.status_code == 201
    assert response.json()["id"] == str(ticket.id)
    service.create_ticket.assert_awaited()


def test_list_tickets_endpoint_filters_by_status(ticket_client):
    client, service = ticket_client
    ticket = _make_ticket(status=TicketStatus.RESOLVED)
    service.list_tickets = AsyncMock(return_value=[ticket])

    response = client.get("/tickets", params={"status": TicketStatus.RESOLVED.value})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == TicketStatus.RESOLVED.value
    service.list_tickets.assert_awaited_with(status=TicketStatus.RESOLVED)


def test_change_status_returns_conflict_on_invalid_transition(ticket_client):
    client, service = ticket_client
    service.change_status = AsyncMock(side_effect=InvalidTicketTransitionError("nope"))

    response = client.post(
        f"/tickets/{uuid4()}/status",
        json={"status": TicketStatus.RESOLVED.value},
    )

    assert response.status_code == 409


def test_get_audit_endpoint_returns_entries(ticket_client):
    client, service = ticket_client
    ticket = _make_ticket()
    audit_entry = _make_audit(ticket.id)
    service.get_audit_log = AsyncMock(return_value=[audit_entry])

    response = client.get(f"/tickets/{ticket.id}/audit")

    assert response.status_code == 200
    assert response.json()[0]["note"] == "created"
