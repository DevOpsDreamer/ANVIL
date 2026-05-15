"""
Strict Pydantic v2 data contracts for deterministic inter-agent handoffs.

Every agent input/output is typed here. LLMs are forced to return
structured JSON matching these schemas — no free-form text passes
between agents.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Webhook Ingress ──────────────────────────────────────────────────────────

class WebhookPayload(BaseModel):
    """Incoming deployment webhook validated at the FastAPI edge."""
    target_url: str = Field(..., description="URL of the deployed staging service")
    deployment_id: str = Field(..., description="Unique deployment identifier")
    repo_url: Optional[str] = Field(None, description="Git clone URL of the target repo")
    auth_signature: Optional[str] = Field(None, description="HMAC signature for payload integrity")


# ── Agent 1: Reconnaissance ──────────────────────────────────────────────────

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class VulnerableEndpoint(BaseModel):
    path: str = Field(..., description="URL path of the vulnerable endpoint")
    method: HttpMethod = Field(..., description="HTTP method to trigger the vulnerability")
    injection_vector: str = Field(..., description="Description of the injection vector")


class ReconOutput(BaseModel):
    """Strict output contract for the Reconnaissance agent."""
    target_url: str = Field(..., description="Base URL of the scanned target")
    detected_framework: str = Field(..., description="Detected web framework or server")
    vulnerable_endpoints: List[VulnerableEndpoint] = Field(
        ..., description="Catalogued attack surface without raw HTTP responses"
    )


# ── Agent 2: Exploitation ────────────────────────────────────────────────────

class ExploitOutput(BaseModel):
    """Strict output contract for the Exploiter agent."""
    vulnerability_confirmed: bool = Field(
        ..., description="Whether the vulnerability was actively confirmed"
    )
    exploit_payload_used: str = Field(
        ..., description="Exact Python exploit code that was executed"
    )
    sandbox_stdout: str = Field(
        ..., description="Raw stdout captured from the sandbox execution"
    )
    extracted_secret: Optional[str] = Field(
        None, description="The secret flag extracted from the target, if any"
    )


# ── Agent 3: Patching ────────────────────────────────────────────────────────

class PatchOutput(BaseModel):
    """Strict output contract for the Patcher agent."""
    file_modified: str = Field(..., description="Relative path to the patched file")
    unified_diff: str = Field(..., description="Unified diff of the applied fix")
    pull_request_title: str = Field(..., description="Title for the generated PR/commit")
    pull_request_body: str = Field(
        ..., description="Body describing the vulnerability and the fix"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Model confidence in the patch correctness"
    )


# ── Verifier ─────────────────────────────────────────────────────────────────

class VerificationResult(BaseModel):
    """Output of the deterministic Verifier node."""
    verified: bool = Field(
        ..., description="True only if the sandbox stdout cryptographically proves exploitation"
    )
    reason: str = Field(..., description="Human-readable justification")
    expected_pattern: Optional[str] = Field(
        None, description="The pattern or hash the Verifier was checking for"
    )
    actual_value: Optional[str] = Field(
        None, description="The actual value found in stdout"
    )


# ── Master State (CPN Token) ────────────────────────────────────────────────

class MasterState(BaseModel):
    """The coloured token that flows through the Petri net."""
    trace_id: str
    task_id: str
    current_node: str = "ingress"
    retry_count: int = 0
    webhook: Optional[WebhookPayload] = None
    recon: Optional[ReconOutput] = None
    exploit: Optional[ExploitOutput] = None
    verification: Optional[VerificationResult] = None
    patch: Optional[PatchOutput] = None
    error: Optional[str] = None
    completed: bool = False
