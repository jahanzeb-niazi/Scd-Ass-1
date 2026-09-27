"""
Centralized runtime configuration, loaded from environment variables / .env.

Everything that varies between local, CI and prod belongs here — never hardcode
a host, port, or credential anywhere else in the app (grep the codebase for
"localhost" before you submit; it's an automatic -8, §5.3).
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "civicpulse-backend"
    environment: str = Field(default="development")  # development | ci | production

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://civicpulse:civicpulse@database:5432/civicpulse"
    )

    # --- Redis (cache + rate limiter, §2.4) ---
    redis_url: str = Field(default="redis://cache:6379/0")
    stats_cache_ttl_seconds: int = 30
    triage_cache_ttl_seconds: int = 60 * 60 * 24  # 24h, §2.5 item 5

    # --- Rate limiting (§2.4 Job 2) ---
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60

    # --- Triage provider selection (§2.5) ---
    # One of: llm | ollama | rules | simulated
    triage_provider: str = Field(default="simulated")
    triage_timeout_seconds: float = 10.0  # hard cap, §2.5 item 2

    # Groq / OpenAI-compatible (recommended primary, §2.5)
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"  # TODO(you): confirm current free-tier model name

    # Gemini (alternative)
    gemini_api_key: str | None = None

    # Ollama (offline path)
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"

    # --- Observability ---
    request_id_header: str = "X-Request-ID"


settings = Settings()

# TODO(you): never log settings.groq_api_key / settings.gemini_api_key anywhere.
# TODO(you): confirm every value above actually comes from env in prod (K8s Secret/ConfigMap),
# never a hardcoded default — the defaults here are for local dev convenience only.
