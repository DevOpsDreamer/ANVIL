"""
FastAPI Webhook Ingress — the entry point for the autonomous pipeline.

Validates incoming deployment webhooks with Pydantic, injects W3C Trace
Context, and instantly dispatches to the Celery queue. Returns HTTP 202.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.schemas import WebhookPayload
from app.telemetry import init_telemetry, inject_trace_context, trace_operation

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Autonomous Red-Team Engine",
    description="Multi-agent defensive remediation pipeline — PS3 Autonomy Track",
    version="0.1.0",
)


@app.on_event("startup")
async def _startup() -> None:
    init_telemetry()
    logger.info("FastAPI ingress ready")


@app.post("/webhook", status_code=202)
async def receive_webhook(payload: WebhookPayload, request: Request):
    """
    Accept a deployment webhook, validate it, and enqueue the pipeline.

    Returns 202 Accepted immediately with the generated Trace ID.
    """
    trace_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex

    with trace_operation(
        "webhook_ingress",
        attributes={
            "trace.id": trace_id,
            "webhook.target_url": payload.target_url,
            "webhook.deployment_id": payload.deployment_id,
        },
    ):
        # Capture W3C traceparent for Celery propagation
        trace_ctx = inject_trace_context()

        # Lazy import to avoid circular dependency at module level
        from app.tasks import run_pipeline

        run_pipeline.apply_async(
            kwargs={
                "trace_id": trace_id,
                "task_id": task_id,
                "webhook_data": payload.model_dump(),
                "trace_context": trace_ctx,
            },
            task_id=task_id,
        )

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "trace_id": trace_id,
            "task_id": task_id,
            "message": "Pipeline dispatched to queue",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
