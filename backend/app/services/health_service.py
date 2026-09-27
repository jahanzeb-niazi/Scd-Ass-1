"""Liveness vs readiness.

Liveness (/health): "is this process alive?" — touches nothing external, so a
slow database can never cause Kubernetes to restart healthy pods in a loop.

Readiness (/ready): "should this pod receive traffic?" — Postgres AND Redis must
be reachable, and the process must not be draining after SIGTERM.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Lifecycle:
    draining: bool = False
    in_flight: int = 0


@dataclass(frozen=True)
class Readiness:
    ready: bool
    checks: dict[str, str] = field(default_factory=dict)

    @property
    def failed(self) -> list[str]:
        return [name for name, state in self.checks.items() if state != "ok"]


class HealthService:
    def __init__(
        self,
        ping_db: Callable[[], bool],
        ping_cache: Callable[[], bool],
        lifecycle: Lifecycle,
    ) -> None:
        self._ping_db = ping_db
        self._ping_cache = ping_cache
        self._lifecycle = lifecycle

    def readiness(self) -> Readiness:
        checks = {
            "postgres": "ok" if self._ping_db() else "unreachable",
            "redis": "ok" if self._ping_cache() else "unreachable",
        }
        if self._lifecycle.draining:
            checks["shutdown"] = "draining"
        return Readiness(ready=all(v == "ok" for v in checks.values()), checks=checks)
