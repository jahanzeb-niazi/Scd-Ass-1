"""
Request-scoped middleware: propagates/generates X-Request-ID (§2.2) and times
each request for the Prometheus latency histogram (§2.2 /metrics).
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.logging_config import request_id_ctx

# TODO(you): wire this counter/histogram into app/routes/health.py's /metrics
# endpoint via prometheus_client (Counter for request count, Histogram for
# request latency, plus a separate histogram for triage latency and a counter
# for fallback occurrences — see §2.2 /metrics requirement).


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(settings.request_id_header) or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # TODO(you): record duration_ms into your Prometheus histogram here
            request_id_ctx.reset(token)

        response.headers[settings.request_id_header] = request_id
        return response
