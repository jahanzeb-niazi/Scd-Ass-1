"""Service-layer exceptions. Routes map these to HTTP status codes."""

from __future__ import annotations

import uuid

from app.domain import Status


class NotFoundError(Exception):
    def __init__(self, complaint_id: uuid.UUID) -> None:
        super().__init__(f"Complaint {complaint_id} not found")
        self.complaint_id = complaint_id


class InvalidTransitionError(Exception):
    def __init__(self, current: Status, target: Status, allowed: list[Status]) -> None:
        if allowed:
            hint = "allowed from " + current.value + ": " + ", ".join(s.value for s in allowed)
        else:
            hint = f"'{current.value}' is a terminal status"
        super().__init__(f"Invalid status transition: {current.value} → {target.value} ({hint})")
        self.current = current
        self.target = target
        self.allowed = allowed
