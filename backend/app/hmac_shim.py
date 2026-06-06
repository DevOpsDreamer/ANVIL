"""
HMAC Attestation Protocol — Orchestrator Side.

Implements the kernel-level proof token scheme described in AEGIS Paper §5.2.
The orchestrator generates a per-execution nonce and HMAC key, injects them
into the sandbox container, and later verifies the attestation token emitted
by the PID-1 shim on genuine exploitation events.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import logging

logger = logging.getLogger(__name__)

# Attestation token line format in sandbox stdout
_ATTESTATION_PATTERN = re.compile(r"HMAC_ATTESTATION:([a-f0-9]{64}):(\d+\.\d+):([\w_]+)")


@dataclass(frozen=True)
class AttestationMaterial:
    """Per-execution cryptographic material for HMAC attestation."""
    key: bytes    # 32-byte HMAC-SHA256 key
    nonce: bytes  # 32-byte random nonce


def generate_attestation_material() -> AttestationMaterial:
    """Generate fresh cryptographic material for a single sandbox execution."""
    return AttestationMaterial(
        key=os.urandom(32),
        nonce=os.urandom(32),
    )


def compute_expected_hmac(
    material: AttestationMaterial,
    event_type: str,
    timestamp: str,
) -> str:
    """Compute the expected HMAC-SHA256 hex digest for a given event."""
    message = material.nonce + event_type.encode("utf-8") + timestamp.encode("utf-8")
    return hmac.new(material.key, message, hashlib.sha256).hexdigest()


def verify_attestation_token(
    stdout: str,
    material: AttestationMaterial,
) -> tuple[bool, Optional[str]]:
    """
    Scan sandbox stdout for HMAC attestation tokens and verify them.
    
    Returns:
        (verified: bool, reason: str | None)
        - (True, None) if a valid attestation token was found
        - (False, reason) if no token found or token is invalid
    """
    matches = _ATTESTATION_PATTERN.findall(stdout)
    if not matches:
        return False, "no_attestation_token_in_stdout"
    
    for token_hex, timestamp, event_type in matches:
        expected = compute_expected_hmac(material, event_type, timestamp)
        if hmac.compare_digest(token_hex, expected):
            logger.info(
                "HMAC attestation verified: event=%s timestamp=%s",
                event_type, timestamp,
            )
            return True, None
    
    return False, "hmac_mismatch"
