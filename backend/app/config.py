"""Application settings, read from the environment (12-factor).

Nothing here has a secret default. Secrets arrive from `.env` (Compose),
a Kubernetes Secret, or GitHub Secrets — never from a file in the repo.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

TriageProviderName = Literal["llm", "ollama", "rules", "simulated"]
SimulatedFailureMode = Literal["none", "error", "timeout", "rate_limit", "malformed", "bad_request"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    # --- service ---------------------------------------------------------
    app_name: str = "civicpulse"
    log_level: str = "INFO"
    # Backend sits behind nginx (Compose) or an Ingress (k8s), so the client IP
    # arrives in X-Forwarded-For. Turn this off if the API is ever exposed directly.
    trust_proxy_headers: bool = True
    # Only needed when a browser calls the API cross-origin (e.g. a Vite dev
    # server without its proxy). With the nginx /api proxy there is no CORS at all.
    cors_origins: list[str] = Field(default_factory=list)
    shutdown_grace_s: int = 20

    # --- postgres --------------------------------------------------------
    # Either give a full DATABASE_URL, or the parts (Compose / k8s Secret).
    database_url: str | None = None
    postgres_host: str = "database"
    postgres_port: int = 5432
    postgres_user: str = "civicpulse"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "civicpulse"
    db_pool_size: int = 5
    db_connect_timeout_s: int = 3

    # --- redis -----------------------------------------------------------
    redis_url: str = "redis://cache:6379/0"
    redis_timeout_s: float = 2.0

    # --- caching / rate limiting -----------------------------------------
    stats_cache_ttl_s: int = 30
    triage_cache_ttl_s: int = 24 * 60 * 60
    rate_limit_requests: int = 10
    rate_limit_window_s: int = 60

    # --- triage ----------------------------------------------------------
    triage_provider: TriageProviderName = "llm"
    triage_timeout_s: float = 10.0
    triage_retry_jitter_min_s: float = 0.2
    triage_retry_jitter_max_s: float = 0.8

    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"

    simulated_failure_mode: SimulatedFailureMode = "none"
    simulated_failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    simulated_seed: int = 42

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            url = self.database_url
            # Accept plain postgres:// URLs and pin the psycopg 3 driver.
            for prefix in ("postgresql://", "postgres://"):
                if url.startswith(prefix):
                    return "postgresql+psycopg://" + url[len(prefix) :]
            return url
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
