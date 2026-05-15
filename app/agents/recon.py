"""
Reconnaissance Agent — scans the target application and catalogs
the attack surface into a strict ReconOutput schema.

Uses the LLM to reason about discovered endpoints and cross-reference
known vulnerability patterns.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import requests
from openai import OpenAI

from app.config import LLM_MODEL, LLM_TEMPERATURE, OPENAI_API_KEY
from app.schemas import ReconOutput
from app.telemetry import trace_operation

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _probe_target(target_url: str) -> str:
    """
    Perform basic HTTP probing of the target to gather raw data
    for the LLM to reason about. Returns a compact summary string.
    """
    findings: list[str] = []

    # Probe common paths
    common_paths = ["/", "/admin", "/login", "/api", "/static", "/files", "/../etc/passwd"]
    for path in common_paths:
        try:
            url = f"{target_url.rstrip('/')}{path}"
            resp = requests.get(url, timeout=3, allow_redirects=False)
            header_info = {
                "server": resp.headers.get("Server", "unknown"),
                "content-type": resp.headers.get("Content-Type", "unknown"),
                "x-powered-by": resp.headers.get("X-Powered-By", "unknown"),
            }
            findings.append(
                f"GET {path} → {resp.status_code} | "
                f"headers={json.dumps(header_info)} | "
                f"body_length={len(resp.text)}"
            )
            # Check for path traversal indicators
            if "root:" in resp.text or "passwd" in resp.text.lower():
                findings.append(f"  ⚠ Possible path traversal at {path}: response contains system file content")
        except requests.RequestException as exc:
            findings.append(f"GET {path} → ERROR: {exc}")

    return "\n".join(findings)


def run_recon(target_url: str) -> ReconOutput:
    """
    Execute reconnaissance against *target_url* and return a typed
    ReconOutput with the catalogued attack surface.
    """
    with trace_operation(
        "recon_agent",
        attributes={"agent.name": "recon", "agent.target_url": target_url},
    ) as span:
        # Step 1: deterministic probe
        probe_data = _probe_target(target_url)
        logger.info("Recon probe complete:\n%s", probe_data)
        span.set_attribute("recon.probe_lines", probe_data.count("\n") + 1)

        # Step 2: LLM-assisted analysis with structured output
        client = _get_client()
        system_prompt = (
            "You are a security reconnaissance agent. Analyze the HTTP probe "
            "results below and identify vulnerable endpoints. Return ONLY valid "
            "JSON matching this schema: {target_url: str, detected_framework: str, "
            "vulnerable_endpoints: [{path: str, method: 'GET'|'POST'|..., injection_vector: str}]}. "
            "Focus on real vulnerabilities like path traversal, injection, SSRF. "
            "Do NOT include raw HTTP responses in your output."
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Target: {target_url}\n\nProbe results:\n{probe_data}"},
            ],
        )

        raw_json = response.choices[0].message.content
        span.set_attribute("llm.prompt_tokens", response.usage.prompt_tokens)
        span.set_attribute("llm.completion_tokens", response.usage.completion_tokens)
        span.set_attribute("agent.decision_rationale", raw_json[:500])

        # Step 3: validate through Pydantic contract
        result = ReconOutput.model_validate_json(raw_json)
        logger.info("Recon found %d vulnerable endpoints", len(result.vulnerable_endpoints))
        return result
