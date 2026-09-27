"""State machine, stats cache and rate limiter — unit level."""

from __future__ import annotations

import fakeredis
import pytest

from app.domain import Status
from app.providers.cache import RedisCache
from app.providers.rate_limiter import RedisFixedWindowRateLimiter
from app.repositories.complaint_repository import StatsSnapshot
from app.services.errors import InvalidTransitionError
from app.services.state_machine import TRANSITIONS, allowed_from, can_transition, is_terminal
from app.services.stats_service import StatsService

OP, IP, RS, RJ = Status.OPEN, Status.IN_PROGRESS, Status.RESOLVED, Status.REJECTED


@pytest.mark.parametrize(("src", "dst"), [(OP, IP), (IP, RS), (OP, RJ), (IP, RJ)])
def test_allowed_transitions(src: Status, dst: Status) -> None:
    assert can_transition(src, dst)


@pytest.mark.parametrize(
    ("src", "dst"),
    [(OP, RS), (IP, OP), (RS, OP), (RS, IP), (RJ, OP), (RJ, IP), (OP, OP), (RS, RJ)],
)
def test_everything_else_is_rejected(src: Status, dst: Status) -> None:
    assert not can_transition(src, dst)


def test_table_covers_every_status_and_terminals_are_terminal() -> None:
    assert set(TRANSITIONS) == set(Status)
    assert is_terminal(RS) and is_terminal(RJ)
    assert allowed_from(OP) == [IP, RJ]


def test_invalid_transition_message_names_the_transition() -> None:
    msg = str(InvalidTransitionError(RS, IP, []))
    assert "resolved → in_progress" in msg


# ------------------------------------------------------------------ stats
def test_stats_read_through_then_invalidate() -> None:
    loads: list[int] = []

    def load() -> StatsSnapshot:
        loads.append(1)
        return StatsSnapshot(total=1, by_category={"water": 1}, by_priority={}, by_status={})

    svc = StatsService(RedisCache(fakeredis.FakeRedis(decode_responses=True)), load, ttl_s=30)
    assert svc.get().cache_hit is False
    second = svc.get()
    assert second.cache_hit is True and len(loads) == 1
    assert second.stats.by_category["electricity"] == 0  # zeros filled in
    svc.invalidate()
    assert svc.get().cache_hit is False and len(loads) == 2


def test_stats_ttl_is_applied() -> None:
    r = fakeredis.FakeRedis(decode_responses=True)
    svc = StatsService(RedisCache(r), lambda: StatsSnapshot(0, {}, {}, {}), ttl_s=30)
    svc.get()
    assert 0 < r.ttl("stats:v1") <= 30


# ------------------------------------------------------------ rate limit
def test_fixed_window_limiter_is_shared_across_instances() -> None:
    r = fakeredis.FakeRedis(decode_responses=True)
    # Two limiter objects = two pods sharing one Redis.
    pod_a = RedisFixedWindowRateLimiter(r, limit=3, window_s=60)
    pod_b = RedisFixedWindowRateLimiter(r, limit=3, window_s=60)
    decisions = [pod_a.hit("p", "1.2.3.4"), pod_b.hit("p", "1.2.3.4"), pod_a.hit("p", "1.2.3.4")]
    assert all(d.allowed for d in decisions)
    blocked = pod_b.hit("p", "1.2.3.4")
    assert not blocked.allowed and blocked.remaining == 0
    assert 1 <= blocked.retry_after_s <= 60
    assert pod_a.hit("p", "5.6.7.8").allowed  # other clients unaffected
