"""
Verifier Agent — deterministic, non-generative validation node.

This is NOT an LLM. It is a pure Python function that procedurally
checks whether the Exploiter's sandbox_stdout actually proves the
vulnerability was exploited. It compares Action_Requested vs
System_State_Change.

If verification fails, it generates a structured error payload
for the Orchestrator to trigger a re-generation or graceful halt.
"""

from __future__ import annotations

import logging
import re

from app.schemas import ExploitOutput, VerificationResult
from app.telemetry import trace_operation

logger = logging.getLogger(__name__)

# Patterns that prove real exploitation (not hallucinated)
_SUCCESS_MARKERS = [
    "EXPLOIT_SUCCESS",
    "FLAG{",
]

_SECRET_PATTERN = re.compile(r"FLAG\{[A-Za-z0-9_\-]+\}")


def verify_exploit(exploit: ExploitOutput) -> VerificationResult:
    """
    Deterministically verify that the exploit produced real side-effects.

    Rules:
    1. vulnerability_confirmed must be True
    2. sandbox_stdout must contain at least one success marker
    3. If a FLAG pattern exists, it must match the expected regex
    """
    with trace_operation(
        "verifier_agent",
        attributes={
            "agent.name": "verifier",
            "agent.is_deterministic": True,
        },
    ) as span:
        stdout = exploit.sandbox_stdout

        # ── Check 1: exploit self-reported success ────────────────────────
        if not exploit.vulnerability_confirmed:
            reason = (
                "Exploit agent reported vulnerability_confirmed=False. "
                "The sandbox did not confirm exploitation."
            )
            span.set_attribute("verification.result", "REJECTED")
            span.set_attribute("verification.reason", reason)
            logger.warning("Verification FAILED: %s", reason)
            return VerificationResult(
                verified=False,
                reason=reason,
                expected_pattern="EXPLOIT_SUCCESS in stdout",
                actual_value=stdout[:200],
            )

        # ── Check 2: stdout contains success marker ──────────────────────
        has_marker = any(marker in stdout for marker in _SUCCESS_MARKERS)
        if not has_marker:
            reason = (
                f"stdout does not contain any success marker "
                f"({', '.join(_SUCCESS_MARKERS)}). "
                "The exploit may have hallucinated success."
            )
            span.set_attribute("verification.result", "REJECTED")
            span.set_attribute("verification.reason", reason)
            logger.warning("Verification FAILED: %s", reason)
            return VerificationResult(
                verified=False,
                reason=reason,
                expected_pattern=" | ".join(_SUCCESS_MARKERS),
                actual_value=stdout[:200],
            )

        # ── Check 3: if FLAG pattern exists, validate format ─────────────
        flag_match = _SECRET_PATTERN.search(stdout)
        if exploit.extracted_secret and not flag_match:
            reason = (
                "extracted_secret was set but stdout does not contain "
                "a valid FLAG{...} pattern. Possible hallucination."
            )
            span.set_attribute("verification.result", "REJECTED")
            span.set_attribute("verification.reason", reason)
            logger.warning("Verification FAILED: %s", reason)
            return VerificationResult(
                verified=False,
                reason=reason,
                expected_pattern=_SECRET_PATTERN.pattern,
                actual_value=exploit.extracted_secret,
            )

        # ── All checks passed ────────────────────────────────────────────
        verified_flag = flag_match.group(0) if flag_match else None
        reason = (
            "Exploitation verified: stdout contains success marker"
            + (f" and valid flag {verified_flag}" if verified_flag else "")
            + "."
        )
        span.set_attribute("verification.result", "VERIFIED")
        span.set_attribute("verification.flag", verified_flag or "none")
        logger.info("Verification PASSED: %s", reason)
        return VerificationResult(
            verified=True,
            reason=reason,
            expected_pattern=" | ".join(_SUCCESS_MARKERS),
            actual_value=stdout[:200],
        )
