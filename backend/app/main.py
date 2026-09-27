"""
App entrypoint. Wiring only — no business logic here.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.routes import complaints, health, meta, stats

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    TODO(you): implement graceful shutdown per §2.2 —
      - On SIGTERM: stop accepting new requests, let in-flight ones finish,
        close the DB connection pool (app.db.session.engine.dispose()), then exit.
      - FastAPI/uvicorn handle SIGTERM -> lifespan shutdown for you already if
        you use `uvicorn ... ` normally; the part you must NOT skip is actually
        awaiting `engine.dispose()` here on shutdown, and giving in-flight
        requests time to finish (this is also why K8s needs
        terminationGracePeriodSeconds + a preStop hook, see k8s/base/backend-deployment.yaml).
    """
    logger.info("startup")
    yield
    logger.info("shutdown")
    # TODO(you): await engine.dispose()


app = FastAPI(title="CivicPulse API", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)

# TODO(you): tighten this for prod — CORS origin should come from settings,
# not "*", once you know your frontend's actual origin (this is exactly the
# "an origin that is not localhost" lesson from §1.3).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(complaints.router)
app.include_router(stats.router)
app.include_router(meta.router)
