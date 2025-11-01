from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from .models import Ticket, TicketAuditEntry
from .pipeline import TicketEmbeddingPipeline, TicketEmbeddingResult
from .repository import TicketRepository
from .state import TicketStateMachine, TicketStatus


class TicketServiceError(RuntimeError):
    """Base error for ticket service issues."""


class TicketNotFoundError(TicketServiceError):
    """Raised when a ticket could not be located."""


class InvalidTicketTransitionError(TicketServiceError):
    """Raised when attempting to transition to an invalid state."""


@dataclass(slots=True)
class TicketService:
    """High level orchestration for ticket lifecycle operations."""

    repository: TicketRepository
    pipeline: TicketEmbeddingPipeline

    async def ensure_schema(self) -> None:
        await self.repository.ensure_schema()

    async def create_ticket(self, *, subject: str, description: str, actor: str) -> Ticket:
        processed = self.pipeline.run(description)
        ticket_id = uuid4()
        status = TicketStateMachine.initial_state()
        return await self.repository.create_ticket(
            ticket_id=ticket_id,
            subject=subject,
            description=description,
            normalized_description=processed.normalized_text,
            embedding=processed.embedding,
            status=status,
            created_by=actor,
        )

    async def get_ticket(self, ticket_id: UUID) -> Ticket:
        ticket = await self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    async def list_tickets(self, *, status: TicketStatus | None = None) -> list[Ticket]:
        return await self.repository.list_tickets(status=status)

    async def update_ticket(
        self,
        ticket_id: UUID,
        *,
        subject: str | None = None,
        description: str | None = None,
        actor: str,
    ) -> Ticket:
        current = await self.repository.get_ticket(ticket_id)
        if current is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")

        new_subject = subject if subject is not None else current.subject
        new_description = description if description is not None else current.description
        if description is not None:
            processed = self.pipeline.run(new_description)
        else:
            processed = TicketEmbeddingResult(
                normalized_text=current.normalized_description,
                embedding=list(current.embedding),
            )

        updated = await self.repository.update_ticket(
            ticket_id=ticket_id,
            subject=new_subject,
            description=new_description,
            normalized_description=processed.normalized_text,
            embedding=processed.embedding,
            updated_by=actor,
        )
        if updated is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")
        return updated

    async def delete_ticket(self, ticket_id: UUID) -> None:
        deleted = await self.repository.delete_ticket(ticket_id)
        if not deleted:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")

    async def change_status(
        self,
        ticket_id: UUID,
        *,
        new_status: TicketStatus,
        actor: str,
        note: str = "",
        metadata: dict[str, str] | None = None,
    ) -> Ticket:
        ticket = await self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")

        if not TicketStateMachine.can_transition(ticket.status, new_status):
            raise InvalidTicketTransitionError(f"Cannot transition {ticket.status} -> {new_status}")

        updated = await self.repository.change_status(
            ticket_id=ticket_id,
            from_status=ticket.status,
            to_status=new_status,
            actor=actor,
            note=note or "Status updated",
            metadata=metadata,
        )
        if updated is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} not found")
        return updated

    async def get_audit_log(self, ticket_id: UUID) -> list[TicketAuditEntry]:
        return await self.repository.get_audit_log(ticket_id)
