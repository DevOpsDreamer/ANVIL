"""
GitHub App Integration.

Handles incoming webhooks from GitHub App installations,
validates payload signatures, and triggers the AEGIS autonomous pipeline.
"""

import hmac
import hashlib
import logging
import os
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.graph import run_pipeline, RunConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["github_app"])

# Optional: Set this in environment to validate webhook payloads
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the GitHub webhook signature using HMAC-SHA256."""
    if not GITHUB_WEBHOOK_SECRET:
        return True # Skip validation if no secret is configured (dev mode)
        
    if not signature_header:
        return False
        
    hash_object = hmac.new(GITHUB_WEBHOOK_SECRET.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

async def _process_github_event(event_type: str, payload: dict):
    """Background task to process the event and trigger the pipeline."""
    if event_type == "push":
        repo_url = payload.get("repository", {}).get("clone_url")
        branch = payload.get("ref", "").replace("refs/heads/", "")
        
        if not repo_url:
            logger.error("No clone_url found in push event")
            return
            
        logger.info(f"Received push event for {repo_url} on branch {branch}")
        
        # Trigger the pipeline (source code mode)
        config = RunConfig(
            repo_url=repo_url,
            entry_point="", # Will be auto-detected or ignored by universal recon
            sandbox_env={}
        )
        try:
            logger.info("Triggering AEGIS autonomous pipeline...")
            # We would typically call run_pipeline here but we don't have an async adapter for it
            # For demo purposes, we will just log it.
            run_pipeline(config)
            logger.info("Pipeline triggered successfully from GitHub push event.")
        except Exception as e:
            logger.error(f"Failed to trigger pipeline: {e}")
            
    elif event_type == "security_advisory":
        action = payload.get("action")
        advisory = payload.get("security_advisory", {})
        cve_id = advisory.get("cve_id")
        
        logger.info(f"Received security_advisory event ({action}) for {cve_id}")
        
        # In a real setup, we would query the GitHub App installations
        # to find which of our repos are using the vulnerable package
        # and then trigger the pipeline on them.
        pass

@router.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for GitHub App Webhooks.
    """
    signature = request.headers.get("x-hub-signature-256", "")
    event_type = request.headers.get("x-github-event", "")
    delivery_id = request.headers.get("x-github-delivery", "")
    
    logger.info(f"Received GitHub webhook: event={event_type}, delivery={delivery_id}")
    
    body = await request.body()
    if not verify_signature(body, signature):
        logger.warning(f"Invalid GitHub webhook signature from {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    # Queue the processing so we return 200 OK immediately to GitHub
    background_tasks.add_task(_process_github_event, event_type, payload)
    
    return {"status": "accepted"}
