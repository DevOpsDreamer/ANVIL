"""
Central configuration for the Autonomous Red-Team Engine.
All secrets and environment toggles live here.
"""

import os

# ── LLM Provider ──────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── SQLite ────────────────────────────────────────────────────────────────────
SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "master_state.db")

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# ── Sandbox ───────────────────────────────────────────────────────────────────
SANDBOX_TIMEOUT_SECONDS: int = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "5"))
SANDBOX_MAX_RETRIES: int = int(os.getenv("SANDBOX_MAX_RETRIES", "3"))

# ── Omium / OpenTelemetry ─────────────────────────────────────────────────────
OMIUM_API_KEY: str = os.getenv(
    "OMIUM_API_KEY",
    "omium_poJ52g3sSBV6Cijv9kAi-HmAsqZiPptZNaSpLfofb-E",
)
OMIUM_ENDPOINT: str = os.getenv(
    "OMIUM_ENDPOINT",
    "ingest.monium.yandex.cloud:443",
)
SERVICE_NAME: str = os.getenv("SERVICE_NAME", "red-team-engine")

# ── Target Application ────────────────────────────────────────────────────────
TARGET_APP_HOST: str = os.getenv("TARGET_APP_HOST", "http://localhost:9999")
TARGET_REPO_DIR: str = os.getenv("TARGET_REPO_DIR", "target_app")

# ── Redis Streams ─────────────────────────────────────────────────────────────
REDIS_TASK_STREAM: str = "agent:tasks"
REDIS_RESULT_STREAM: str = "agent:results"
REDIS_CONSUMER_GROUP: str = "orchestrator-group"
