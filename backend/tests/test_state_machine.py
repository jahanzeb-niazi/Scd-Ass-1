"""
Cheap, high-value tests — the transition table is small, cover it completely.
"""
import pytest

from app.db.models import Status
from app.services.state_machine import InvalidTransitionError, validate_transition


@pytest.mark.parametrize(
    "current,attempted",
    [
        (Status.OPEN, Status.IN_PROGRESS),
        (Status.OPEN, Status.REJECTED),
        (Status.IN_PROGRESS, Status.RESOLVED),
        (Status.IN_PROGRESS, Status.REJECTED),
    ],
)
def test_legal_transitions_do_not_raise(current, attempted):
    validate_transition(current, attempted)  # should not raise


@pytest.mark.parametrize(
    "current,attempted",
    [
        (Status.OPEN, Status.RESOLVED),         # must go through in_progress
        (Status.RESOLVED, Status.OPEN),          # terminal
        (Status.REJECTED, Status.OPEN),          # terminal
        (Status.IN_PROGRESS, Status.OPEN),       # no backward transition
        (Status.OPEN, Status.OPEN),              # no-op transition
    ],
)
def test_illegal_transitions_raise(current, attempted):
    with pytest.raises(InvalidTransitionError):
        validate_transition(current, attempted)
