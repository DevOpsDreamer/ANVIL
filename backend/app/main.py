"""
FastAPI application — entry point for the Anvil web app (AEGIS v8).

Serves the API routes for GitHub OAuth, scan management, and SSE streaming.
The frontend (Vite app) will be served separately or proxied.

Changes from v1:
  * Replaced deprecated ``@app.on_event`` with the ``lifespan`` async
    context-manager pattern.
  * Fail-fast on missing ``OPENAI_API_KEY``; warn on default session secret.
  * Tightened CORS: explicit methods & headers instead of wildcards.
  * Imported ``allowlist`` module for ingress hardening (enforcement is
    in ``api.py``).
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.auth import router as auth_router
from app.config import FRONTEND_URL, OPENAI_API_KEY, SESSION_SECRET
from app.telemetry import init_telemetry

# Imported for side-effect: loads the domain allowlist at startup.
# Scan endpoint enforcement lives in api.py.
import app.allowlist  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (replaces deprecated @app.on_event) ────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    # ── Startup validation ───────────────────────────────────────────────
    if not OPENAI_API_KEY:
        logger.critical(
            "OPENAI_API_KEY is not set — the pipeline cannot call the LLM. "
            "Aborting startup."
        )
        sys.exit(1)

    _DEFAULT_SECRET = "change-me-in-production-32bytes!"
    if SESSION_SECRET == _DEFAULT_SECRET:
        logger.warning(
            "SESSION_SECRET is still the default placeholder — "
            "set a unique value before deploying to production"
        )

    init_telemetry()
    logger.info("Anvil API server ready")

    yield  # ← application is running

    # (shutdown logic, if any, goes here)
    logger.info("Anvil API server shutting down")


# ── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Anvil — Autonomous Security Remediation",
    description=(
        "Multi-agent CPN pipeline that scans GitHub repos for vulnerabilities, "
        "generates exploits, verifies them, and creates Pull Requests with fixes."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS — allow the Vite dev server to call the API ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://localhost:3000",   # alternate
        "http://localhost:8000",   # same-origin
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Cookie",
    ],
)

# ── Mount routers ────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "anvil"}


# ── Legacy webhook endpoint (kept for backward compatibility) ────────────────

@app.post("/webhook", status_code=202, tags=["legacy"])
async def receive_webhook_legacy(payload: dict):
    """
    Legacy webhook endpoint. For new integrations, use POST /api/scan instead.
    """
    import uuid

    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "message": "Legacy webhook received. Use POST /api/scan for the web app.",
            "trace_id": uuid.uuid4().hex,
        },
    )
