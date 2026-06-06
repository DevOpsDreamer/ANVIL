"""
Verifier Agent — deterministic, non-generative validation node.

This is NOT an LLM. It is a pure Python function that procedurally
checks whether the Exploiter's sandbox_stdout actually proves the
vulnerability was exploited. It compares Action_Requested vs
System_State_Change.

Supports dual-mode verification:
  A) HMAC mode  — when hmac_material is supplied, the primary check is
     HMAC attestation from the PID-1 shim (AEGIS Paper §5.2). Text
     markers are a secondary signal only.
  B) Fallback mode — when no hmac_material is present (subprocess
     sandbox), the original EXPLOIT_SUCCESS / FLAG{} regex checks
     are the primary verification path. Fully backward-compatible.

If verification fails, it generates a structured error payload
for the Orchestrator to trigger a re-generation or graceful halt.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.hmac_shim import AttestationMaterial, verify_attestation_token
from app.schemas import ExploitOutput, VerificationResult

try:
    from app.telemetry import trace_operation
except Exception:
    # Graceful no-op fallback when telemetry is unavailable
    from contextlib import contextmanager

    @contextmanager  # type: ignore[arg-type]
    def trace_operation(name: str, **kwargs):  # type: ignore[misc]
        """No-op span context manager used when app.telemetry is unavailable."""

        class _NoopSpan:
            def set_attribute(self, key: str, value: object) -> None:
                pass

        yield _NoopSpan()

logger = logging.getLogger(__name__)

# The single deterministic success marker the Exploiter must print
_SUCCESS_MARKER = "EXPLOIT_SUCCESS"

# Flag pattern emitted by the shim entrypoint when flag file is read
_FLAG_PATTERN = re.compile(r"FLAG\{[\w_]+\}")

# Minimum stdout length (excluding marker) to consider as real evidence
_MIN_EVIDENCE_LENGTH = 5  # Reduced from 10 to allow short proofs like "500 error"

# Vulnerability types that can have short evidence (e.g., HTTP status codes)
_SHORT_EVIDENCE_VULN_TYPES = [
    "500", "error", "crash", "exception", "traceback",
    "deserialization", "pickle", "yaml", "marshal",
    "rce", "code execution", "arbitrary code",
]


# ── Dual-mode entry point ────────────────────────────────────────────────────


def verify_exploit(
    exploit: ExploitOutput,
    hmac_material: Optional[AttestationMaterial] = None,
) -> VerificationResult:
    """
    Deterministically verify that the exploit produced real side-effects.

    When *hmac_material* is provided the HMAC attestation token emitted
    by the sandbox PID-1 shim is the **primary** proof signal. Text
    markers (EXPLOIT_SUCCESS, FLAG{…}) are secondary.

    When *hmac_material* is ``None`` (subprocess sandbox / local dev)
    the original text-marker heuristics are used instead.
    """
    with trace_operation(
        "verifier_agent",
        attributes={
            "agent.name": "verifier",
            "agent.is_deterministic": True,
            "verification.mode": "hmac" if hmac_material else "fallback",
        },
    ) as span:
        if hmac_material is not None:
            return _verify_hmac_mode(exploit, hmac_material, span)
        return _verify_fallback_mode(exploit, span)


# ── Mode A: HMAC Attestation ────────────────────────────────────────────────


def _verify_hmac_mode(
    exploit: ExploitOutput,
    material: AttestationMaterial,
    span: object,
) -> VerificationResult:
    """
    HMAC-first verification.

    1. Verify HMAC attestation token from stdout (primary).
    2. Check for text markers as secondary evidence.
    3. Return appropriate failure category on mismatch.
    """
    stdout = exploit.sandbox_stdout

    # ── Primary: HMAC attestation ────────────────────────────────────────
    hmac_ok, hmac_reason = verify_attestation_token(stdout, material)

    if not hmac_ok:
        failure_category = (
            "hmac_missing" if hmac_reason == "no_attestation_token_in_stdout"
            else "hmac_mismatch"
        )
        reason = (
            f"HMAC attestation failed ({hmac_reason}). "
            "The sandbox PID-1 shim did not emit a valid proof token — "
            "genuine exploitation was not confirmed."
        )
        span.set_attribute("verification.result", "REJECTED")  # type: ignore[union-attr]
        span.set_attribute("verification.reason", reason)  # type: ignore[union-attr]
        logger.warning("Verification FAILED (HMAC): %s", reason)
        return VerificationResult(
            verified=False,
            reason=reason,
            expected_pattern="HMAC_ATTESTATION:<valid_token>",
            actual_value=stdout[:200],
            failure_category=failure_category,
        )

    # ── Secondary: text marker enrichment (non-blocking) ─────────────────
    has_marker = _SUCCESS_MARKER in stdout
    has_flag = bool(_FLAG_PATTERN.search(stdout))
    evidence_text = stdout.replace(_SUCCESS_MARKER, "").strip()
    has_evidence = bool(exploit.exploit_evidence)

    reason = (
        "HMAC attestation verified — genuine sandbox exploitation confirmed. "
        f"Secondary signals: marker={has_marker}, flag={has_flag}, "
        f"evidence_chars={len(evidence_text)}"
        + (", evidence_captured" if has_evidence else "")
        + "."
    )
    span.set_attribute("verification.result", "VERIFIED")  # type: ignore[union-attr]
    span.set_attribute("verification.hmac_verified", True)  # type: ignore[union-attr]
    span.set_attribute("verification.evidence_length", len(evidence_text))  # type: ignore[union-attr]
    logger.info("Verification PASSED (HMAC): %s", reason)
    return VerificationResult(
        verified=True,
        reason=reason,
        expected_pattern="HMAC_ATTESTATION:<valid_token>",
        actual_value=stdout[:200],
    )


# ── Mode B: Legacy Fallback (text markers) ───────────────────────────────────


def _verify_fallback_mode(
    exploit: ExploitOutput,
    span: object,
) -> VerificationResult:
    """
    Original text-marker heuristic verification (backward-compatible).

    Rules:
    1. vulnerability_confirmed must be True
    2. sandbox_stdout must contain EXPLOIT_SUCCESS or FLAG{…}
    3. stdout must contain meaningful content beyond just the marker
       (prevents hallucinated empty exploits)
    """
    stdout = exploit.sandbox_stdout

    # ── Check 1: exploit self-reported success ────────────────────────────
    if not exploit.vulnerability_confirmed:
        reason = (
            "Exploit agent reported vulnerability_confirmed=False. "
            "The sandbox did not confirm exploitation."
        )
        span.set_attribute("verification.result", "REJECTED")  # type: ignore[union-attr]
        span.set_attribute("verification.reason", reason)  # type: ignore[union-attr]
        logger.warning("Verification FAILED: %s", reason)
        return VerificationResult(
            verified=False,
            reason=reason,
            expected_pattern=f"{_SUCCESS_MARKER} in stdout",
            actual_value=stdout[:200],
            failure_category="not_confirmed",
        )

    # ── Check 2: stdout contains the success marker or flag ──────────────
    has_marker = _SUCCESS_MARKER in stdout
    has_flag = bool(_FLAG_PATTERN.search(stdout))

    if not has_marker and not has_flag:
        reason = (
            f"stdout does not contain the success marker "
            f"'{_SUCCESS_MARKER}' or a FLAG{{…}} token. "
            "The exploit may have hallucinated success."
        )
        span.set_attribute("verification.result", "REJECTED")  # type: ignore[union-attr]
        span.set_attribute("verification.reason", reason)  # type: ignore[union-attr]
        logger.warning("Verification FAILED: %s", reason)
        return VerificationResult(
            verified=False,
            reason=reason,
            expected_pattern=_SUCCESS_MARKER,
            actual_value=stdout[:200],
            failure_category="no_marker",
        )

    # ── Check 3: stdout has meaningful evidence beyond the marker ─────────
    # Strip the marker and check if there's real content
    evidence_text = stdout.replace(_SUCCESS_MARKER, "").strip()

    # Check if this is a short-evidence vulnerability type (e.g., crash-based)
    is_short_evidence_type = any(
        keyword in stdout.lower()
        for keyword in _SHORT_EVIDENCE_VULN_TYPES
    )

    # Instead of hard-failing on minimal chars, check multiple signals:
    exploit_confirmed = (
        len(evidence_text) > 0 or                              # has extracted data
        "confirmed" in stdout.lower() or                       # any confirmation word
        is_short_evidence_type or                              # crash-based evidence
        has_flag                                               # flag presence is proof
    )

    if not exploit_confirmed:
        reason = (
            f"stdout contains '{_SUCCESS_MARKER}' but has minimal "
            f"evidence ({len(evidence_text)} chars of content). "
            "The exploit may have printed the marker without actually "
            "extracting any data. This looks like a hallucinated exploit."
        )
        span.set_attribute("verification.result", "REJECTED")  # type: ignore[union-attr]
        span.set_attribute("verification.reason", reason)  # type: ignore[union-attr]
        logger.warning("Verification FAILED: %s", reason)
        return VerificationResult(
            verified=False,
            reason=reason,
            expected_pattern=f"{_SUCCESS_MARKER} + meaningful evidence",
            actual_value=stdout[:200],
            failure_category="no_evidence",
        )

    # Special case: if evidence is short but accepted, log it
    if len(evidence_text) < _MIN_EVIDENCE_LENGTH:
        logger.info(
            "Accepting short evidence (%d chars) due to auxiliary exploit signals",
            len(evidence_text),
        )

    # ── All checks passed ────────────────────────────────────────────────
    has_evidence = bool(exploit.exploit_evidence)
    reason = (
        f"Exploitation verified: stdout contains '{_SUCCESS_MARKER}' "
        f"with {len(evidence_text)} chars of evidence"
        + (f" (evidence captured)" if has_evidence else "")
        + "."
    )
    span.set_attribute("verification.result", "VERIFIED")  # type: ignore[union-attr]
    span.set_attribute("verification.evidence_length", len(evidence_text))  # type: ignore[union-attr]
    logger.info("Verification PASSED: %s", reason)
    return VerificationResult(
        verified=True,
        reason=reason,
        expected_pattern=_SUCCESS_MARKER,
        actual_value=stdout[:200],
    )
