"""Ticket service domain models and services."""

from .models import Ticket, TicketAuditEntry
from .service import TicketService, TicketNotFoundError, InvalidTicketTransitionError
from .state import TicketStatus, TicketStateMachine

__all__ = [
    "Ticket",
    "TicketAuditEntry",
    "TicketService",
    "TicketNotFoundError",
    "InvalidTicketTransitionError",
    "TicketStatus",
    "TicketStateMachine",
]
