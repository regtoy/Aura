import pytest

from app.tickets.state import TicketStateMachine, TicketStatus


def test_ticket_state_machine_allows_expected_transitions():
    assert TicketStateMachine.can_transition(TicketStatus.NEW, TicketStatus.TRIAGED)
    assert TicketStateMachine.can_transition(TicketStatus.TRIAGED, TicketStatus.IN_PROGRESS)
    assert TicketStateMachine.can_transition(TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED)
    assert TicketStateMachine.can_transition(TicketStatus.RESOLVED, TicketStatus.CLOSED)
    assert TicketStateMachine.can_transition(TicketStatus.CLOSED, TicketStatus.CLOSED)


def test_ticket_state_machine_blocks_invalid_transitions():
    assert not TicketStateMachine.can_transition(TicketStatus.CLOSED, TicketStatus.NEW)
    with pytest.raises(ValueError):
        TicketStateMachine.assert_transition(TicketStatus.CLOSED, TicketStatus.TRIAGED)
