"""
Structured JSON logging to stdout (§2.2: "never to a file, because a container's
filesystem is ephemeral"). request_id is injected via contextvars so every log
line inside a request carries it, propagated from the X-Request-ID header
(middleware.py generates one if absent).
"""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


# TODO(you): make sure every triage fallback logs exactly one WARNING with
# complaint id, provider name, and error class (§2.2). Example:
#
#   logger.warning(
#       "triage_fallback",
#       extra={"complaint_id": str(complaint_id), "provider": provider.name,
#              "error_class": type(exc).__name__},
#   )
