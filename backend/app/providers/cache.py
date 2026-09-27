"""Redis-backed cache provider (job 1: read-through cache; also triage cache,
hit-rate counters and the recent-outcomes ring buffer).

Services depend on the `Cache` protocol, so tests can pass fakeredis or a stub.
All Redis failures surface as `CacheError`; callers decide whether to degrade.
"""

from __future__ import annotations

from typing import Protocol, cast

import redis
from redis.backoff import ConstantBackoff
from redis.retry import Retry


class CacheError(Exception):
    pass


def build_redis_client(url: str, timeout_s: float) -> redis.Redis:
    """One Redis client for cache and rate limiter.

    redis-py's default retry policy backs off several times per command. During
    a Redis outage that turns every request into a multi-second wait, so we
    allow a single quick retry and then let the caller degrade.
    """
    return redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=timeout_s,
        socket_connect_timeout=timeout_s,
        health_check_interval=30,
        retry=Retry(ConstantBackoff(0.05), retries=1),
    )


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_s: int) -> None: ...
    def delete(self, *keys: str) -> None: ...
    def incr(self, key: str) -> int: ...
    def get_int(self, key: str) -> int: ...
    def push_capped(self, key: str, value: str, maxlen: int) -> None: ...
    def list_range(self, key: str, count: int) -> list[str]: ...
    def ping(self) -> bool: ...


class RedisCache:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    @classmethod
    def from_url(cls, url: str, timeout_s: float) -> RedisCache:
        return cls(build_redis_client(url, timeout_s))

    @property
    def client(self) -> redis.Redis:
        return self._r

    def get(self, key: str) -> str | None:
        try:
            return cast("str | None", self._r.get(key))
        except redis.RedisError as exc:
            raise CacheError(type(exc).__name__) from exc

    def set(self, key: str, value: str, ttl_s: int) -> None:
        try:
            self._r.set(key, value, ex=ttl_s)
        except redis.RedisError as exc:
            raise CacheError(type(exc).__name__) from exc

    def delete(self, *keys: str) -> None:
        try:
            self._r.delete(*keys)
        except redis.RedisError as exc:
            raise CacheError(type(exc).__name__) from exc

    def incr(self, key: str) -> int:
        try:
            return int(self._r.incr(key))
        except redis.RedisError as exc:
            raise CacheError(type(exc).__name__) from exc

    def get_int(self, key: str) -> int:
        value = self.get(key)
        return int(value) if value else 0

    def push_capped(self, key: str, value: str, maxlen: int) -> None:
        try:
            pipe = self._r.pipeline(transaction=True)
            pipe.lpush(key, value)
            pipe.ltrim(key, 0, maxlen - 1)
            pipe.execute()
        except redis.RedisError as exc:
            raise CacheError(type(exc).__name__) from exc

    def list_range(self, key: str, count: int) -> list[str]:
        try:
            return cast("list[str]", self._r.lrange(key, 0, count - 1))
        except redis.RedisError as exc:
            raise CacheError(type(exc).__name__) from exc

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except redis.RedisError:
            return False

    def close(self) -> None:
        self._r.close()
