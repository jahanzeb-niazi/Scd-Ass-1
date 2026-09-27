"""Complaint status state machine, as an explicit transition table.

    open ──► in_progress ──► resolved
      │           │
      └──► rejected ◄┘

resolved and rejected are terminal. Anything not in the table is a 409.
The frontend never duplicates this table: each complaint returned by the API
carries `allowed_transitions`, computed here.
"""

from __future__ import annotations

from types import MappingProxyType

from app.domain import Status

TRANSITIONS: MappingProxyType[Status, frozenset[Status]] = MappingProxyType(
    {
        Status.OPEN: frozenset({Status.IN_PROGRESS, Status.REJECTED}),
        Status.IN_PROGRESS: frozenset({Status.RESOLVED, Status.REJECTED}),
        Status.RESOLVED: frozenset(),
        Status.REJECTED: frozenset(),
    }
)

# Stable display order for allowed_transitions in API responses.
_ORDER = (Status.OPEN, Status.IN_PROGRESS, Status.RESOLVED, Status.REJECTED)


def can_transition(current: Status, target: Status) -> bool:
    return target in TRANSITIONS[current]


def allowed_from(current: Status) -> list[Status]:
    allowed = TRANSITIONS[current]
    return [s for s in _ORDER if s in allowed]


def is_terminal(status: Status) -> bool:
    return not TRANSITIONS[status]
