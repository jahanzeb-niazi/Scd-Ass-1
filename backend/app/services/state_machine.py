"""
Explicit transition table for complaint status (§2.2 domain rules), NOT a
chain of if-statements. resolved and rejected are terminal.

    open -> in_progress
    open -> rejected
    in_progress -> resolved
    in_progress -> rejected

Everything else must raise InvalidTransitionError, which the route layer
turns into a 409 naming the attempted transition.
"""
from __future__ import annotations

from app.db.models import Status

ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.OPEN: {Status.IN_PROGRESS, Status.REJECTED},
    Status.IN_PROGRESS: {Status.RESOLVED, Status.REJECTED},
    Status.RESOLVED: set(),   # terminal
    Status.REJECTED: set(),   # terminal
}


class InvalidTransitionError(Exception):
    def __init__(self, current: Status, attempted: Status) -> None:
        self.current = current
        self.attempted = attempted
        super().__init__(f"cannot transition from {current.value} to {attempted.value}")


def validate_transition(current: Status, attempted: Status) -> None:
    if attempted not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(current, attempted)


# TODO(you): write tests/test_state_machine.py covering every legal transition
# AND every illegal one (including same-state "transitions" and transitions
# out of terminal states) — this table is small enough that 100% coverage of
# it is cheap and expected.
