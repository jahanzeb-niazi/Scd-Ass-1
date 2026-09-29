"""FastAPI application factory."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.container import Container
from app.logging_config import configure_logging, request_id_var
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.routes import complaints, health, stats
from app.routes.errors import install_error_handlers

log = logging.getLogger("civicpulse.http")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")
_QUIET_PATHS = {"/health", "/ready", "/metrics"}  # probes: log at DEBUG, not INFO


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        c = container or Container.build(settings)
        app.state.container = c
        log.info(
            "startup complete",
            extra={"triage_provider": c.triage.provider.name, "fallback": c.triage.fallback.name},
        )
        try:
            yield
        finally:
            # Runs after uvicorn has stopped accepting connections and drained
            # in-flight requests (see app/__main__.py).
            if container is None:
                c.close()
            log.info("shutdown complete")

    app = FastAPI(
        title="CivicPulse API",
        version="0.1.0",
        description="Municipal complaint intake, AI triage and operations.",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Cache", "X-Request-ID", "Retry-After"],
        )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        lifecycle = getattr(getattr(request.app.state, "container", None), "lifecycle", None)
        if lifecycle is not None:
            lifecycle.in_flight += 1
        started = time.perf_counter()
        status = 500
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # Handle here, inside the request context, so the log line and
                # the 500 body both carry this request's id.
                log.exception("unhandled error", extra={"error_class": type(exc).__name__})
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error", "request_id": rid},
                )
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, route_path, str(status)).inc()
            HTTP_LATENCY.labels(request.method, route_path).observe(elapsed)
            if lifecycle is not None:
                lifecycle.in_flight -= 1
            log.log(
                logging.DEBUG if request.url.path in _QUIET_PATHS else logging.INFO,
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round(elapsed * 1000, 1),
                },
            )
            request_id_var.reset(token)

    install_error_handlers(app)
    app.include_router(complaints.router)
    app.include_router(stats.router)
    app.include_router(health.router)
    _document_400_not_422(app)
    return app


def _document_400_not_422(app: FastAPI) -> None:
    """FastAPI documents validation failures as 422; this API returns 400 with
    ValidationErrorOut (routes/errors.py). Fix the published contract so the
    frontend's generated client is typed against what the server really sends."""
    original = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original()
        for path_item in schema.get("paths", {}).values():
            for op in path_item.values():
                if isinstance(op, dict):
                    op.get("responses", {}).pop("422", None)
        comps = schema.get("components", {}).get("schemas", {})
        comps.pop("HTTPValidationError", None)
        comps.pop("ValidationError", None)
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]


def build() -> FastAPI:
    """Entry point for `uvicorn --factory app.main:build` (dev hot reload)."""
    settings = get_settings()
    configure_logging(settings.log_level)
    return create_app(settings)
