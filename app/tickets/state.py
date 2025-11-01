from __future__ import annotations

from enum import Enum


class TicketStatus(str, Enum):
    """Supported states for a ticket's lifecycle."""

    NEW = "new"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketStateMachine:
    """Validate ticket lifecycle transitions."""

    _TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
        TicketStatus.NEW: {TicketStatus.TRIAGED, TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
        TicketStatus.TRIAGED: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED},
        TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.CLOSED},
        TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.IN_PROGRESS},
        TicketStatus.CLOSED: set(),
    }

    @classmethod
    def initial_state(cls) -> TicketStatus:
        return TicketStatus.NEW

    @classmethod
    def can_transition(cls, current: TicketStatus, new: TicketStatus) -> bool:
        if current == new:
            return True
        return new in cls._TRANSITIONS.get(current, set())

    @classmethod
    def assert_transition(cls, current: TicketStatus, new: TicketStatus) -> None:
        if not cls.can_transition(current, new):
            raise ValueError(f"Invalid ticket status transition: {current!s} -> {new!s}")
