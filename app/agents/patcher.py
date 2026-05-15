"""
Patcher Agent — generates a code patch using AST modification,
applies it to the target repository, and creates a Git commit.

Instead of generating raw code strings (error-prone), the LLM produces
a Python script that uses the `ast` module to programmatically rewrite
the vulnerable node in the target file.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from openai import OpenAI

from app.config import LLM_MODEL, LLM_TEMPERATURE, OPENAI_API_KEY, TARGET_REPO_DIR
from app.schemas import ExploitOutput, PatchOutput, ReconOutput, VerificationResult
from app.telemetry import trace_operation

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _run_git(repo_dir: str, *args: str) -> str:
    """Run a git command in *repo_dir* and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def run_patch(
    recon: ReconOutput,
    exploit: ExploitOutput,
    verification: VerificationResult,
    trace_id: str,
) -> PatchOutput:
    """
    Generate and apply a patch to fix the exploited vulnerability,
    then commit it to the target repository.
    """
    with trace_operation(
        "patcher_agent",
        attributes={
            "agent.name": "patcher",
            "agent.target_url": recon.target_url,
            "agent.trace_id": trace_id,
        },
    ) as span:
        repo_dir = os.path.abspath(TARGET_REPO_DIR)

        # Step 1: create a fix branch
        branch_name = f"fix/{trace_id[:12]}"
        try:
            _run_git(repo_dir, "checkout", "-b", branch_name)
        except RuntimeError:
            # Branch might already exist
            _run_git(repo_dir, "checkout", branch_name)

        # Step 2: read the vulnerable source file
        target_file = Path(repo_dir) / "server.py"
        original_code = target_file.read_text(encoding="utf-8")

        # Step 3: ask LLM for the fix
        client = _get_client()

        system_prompt = (
            "You are a security patch agent. Given the vulnerable source code and "
            "the exploit details, generate a fixed version of the code that eliminates "
            "the vulnerability. Return ONLY valid JSON:\n"
            "{\n"
            '  "fixed_code": "<the complete fixed source code>",\n'
            '  "explanation": "<brief explanation of what was fixed>",\n'
            '  "confidence": <float 0-1>\n'
            "}\n"
            "The fix should:\n"
            "1. Sanitize user input to prevent the exploit\n"
            "2. Keep all other functionality intact\n"
            "3. Use secure coding practices (path canonicalization, input validation)\n"
        )

        user_prompt = (
            f"## Vulnerable Code\n```python\n{original_code}\n```\n\n"
            f"## Exploit Details\n"
            f"- Vulnerability type: {recon.vulnerable_endpoints[0].injection_vector if recon.vulnerable_endpoints else 'unknown'}\n"
            f"- Exploit payload:\n```python\n{exploit.exploit_payload_used}\n```\n"
            f"- Sandbox stdout: {exploit.sandbox_stdout[:500]}\n"
            f"- Verification: {verification.reason}\n"
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = json.loads(response.choices[0].message.content)
        fixed_code = raw["fixed_code"]
        explanation = raw["explanation"]
        confidence = float(raw.get("confidence", 0.8))

        span.set_attribute("llm.prompt_tokens", response.usage.prompt_tokens)
        span.set_attribute("llm.completion_tokens", response.usage.completion_tokens)
        span.set_attribute("agent.decision_rationale", explanation[:500])

        # Step 4: write the fixed code
        target_file.write_text(fixed_code, encoding="utf-8")
        logger.info("Patched %s", target_file)

        # Step 5: generate unified diff
        diff = _run_git(repo_dir, "diff", "server.py")

        # Step 6: commit the fix
        pr_title = f"fix: patch {recon.vulnerable_endpoints[0].injection_vector if recon.vulnerable_endpoints else 'vulnerability'} — trace {trace_id[:12]}"
        pr_body = (
            f"## Vulnerability Report\n\n"
            f"**Target**: {recon.target_url}\n"
            f"**Framework**: {recon.detected_framework}\n"
            f"**Vector**: {recon.vulnerable_endpoints[0].injection_vector if recon.vulnerable_endpoints else 'N/A'}\n\n"
            f"## Proof of Exploitation\n\n"
            f"```\n{exploit.sandbox_stdout[:1000]}\n```\n\n"
            f"## Fix Applied\n\n{explanation}\n\n"
            f"**Confidence**: {confidence:.0%}\n"
            f"**Trace ID**: `{trace_id}`\n"
        )

        _run_git(repo_dir, "add", "server.py")
        _run_git(repo_dir, "commit", "-m", pr_title)

        span.set_attribute("patch.branch", branch_name)
        span.set_attribute("patch.confidence", confidence)

        result = PatchOutput(
            file_modified="server.py",
            unified_diff=diff,
            pull_request_title=pr_title,
            pull_request_body=pr_body,
            confidence_score=confidence,
        )

        logger.info("Patch committed on branch %s (confidence=%.0f%%)", branch_name, confidence * 100)
        return result
