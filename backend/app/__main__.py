"""Production entrypoint: `python -m app`.

Graceful shutdown on SIGTERM (what Kubernetes sends on a rolling update):
  1. mark the pod as draining, so /ready returns 503 and it leaves Service endpoints;
  2. uvicorn stops accepting new connections and waits for in-flight requests
     (bounded by SHUTDOWN_GRACE_S, which must be < terminationGracePeriodSeconds);
  3. the lifespan shutdown closes the triage pool, Redis and the DB pool;
  4. the process exits 0.
"""

from __future__ import annotations

import logging
import os
import signal
from types import FrameType

import uvicorn

from app.config import get_settings
from app.logging_config import configure_logging
from app.main import create_app

log = logging.getLogger("civicpulse.lifecycle")


class GracefulServer(uvicorn.Server):
    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        container = (
            getattr(self.config.loaded_app.state, "container", None) if self.config.loaded else None
        )
        lifecycle = getattr(container, "lifecycle", None)
        if lifecycle is not None and not lifecycle.draining:
            lifecycle.draining = True
            log.info(
                "signal received; draining",
                extra={"signal": signal.Signals(sig).name, "in_flight": lifecycle.in_flight},
            )
        super().handle_exit(sig, frame)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = create_app(settings)
    config = uvicorn.Config(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),  # noqa: S104 — container must listen on all interfaces
        port=int(os.environ.get("PORT", "8000")),
        log_config=None,  # keep our JSON logging
        access_log=False,  # our middleware writes the access log with request_id
        # Client-IP resolution for rate limiting is done explicitly in app/deps.py.
        proxy_headers=False,
        timeout_graceful_shutdown=settings.shutdown_grace_s,
    )
    GracefulServer(config).run()


if __name__ == "__main__":
    main()
