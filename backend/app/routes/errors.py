"""Mapping service/domain exceptions to HTTP responses."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import request_id_var
from app.services.errors import InvalidTransitionError, NotFoundError

log = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    def __init__(self, retry_after_s: int, limit: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after_s = retry_after_s
        self.limit = limit


def _field(loc: tuple[object, ...]) -> str:
    # ("body", "text") -> "text"; ("query", "page_size") -> "page_size"
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": _field(tuple(e.get("loc", ()))),
                "message": str(e.get("msg", "invalid")).removeprefix("Value error, "),
                "type": str(e.get("type", "value_error")),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Validation failed",
                "errors": errors,
                "request_id": request_id_var.get(),
            },
        )

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": str(exc), "request_id": request_id_var.get()}
        )

    @app.exception_handler(InvalidTransitionError)
    async def _conflict(_: Request, exc: InvalidTransitionError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "current": exc.current.value,
                "attempted": exc.target.value,
                "allowed": [s.value for s in exc.allowed],
                "request_id": request_id_var.get(),
            },
        )

    @app.exception_handler(RateLimitExceededError)
    async def _rate_limited(_: Request, exc: RateLimitExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            headers={
                "Retry-After": str(exc.retry_after_s),
                "X-RateLimit-Limit": str(exc.limit),
                "X-RateLimit-Remaining": "0",
            },
            content={
                "detail": (
                    f"Too many complaints from this address: limit is {exc.limit} per window. "
                    f"Try again in {exc.retry_after_s} s."
                ),
                "retry_after_s": exc.retry_after_s,
                "request_id": request_id_var.get(),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc.detail), "request_id": request_id_var.get()},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"error_class": type(exc).__name__})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id_var.get()},
        )
