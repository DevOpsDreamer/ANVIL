import pytest
from app.agents.verifier import verify_exploit
from app.schemas import ExploitOutput
from app.hmac_shim import AttestationMaterial, compute_expected_hmac
import time

def test_verifier_fallback_mode_success():
    exploit = ExploitOutput(
        vulnerability_confirmed=True,
        exploit_payload_used="print('EXPLOIT_SUCCESS')",
        sandbox_stdout="EXPLOIT_SUCCESS\nExtracted root password: password123",
        attempt_number=1
    )
    result = verify_exploit(exploit)
    assert result.verified is True
    assert result.failure_category is None

def test_verifier_fallback_mode_no_marker():
    exploit = ExploitOutput(
        vulnerability_confirmed=True,
        exploit_payload_used="print('fail')",
        sandbox_stdout="Internal Server Error",
        attempt_number=1
    )
    result = verify_exploit(exploit)
    assert result.verified is False
    assert result.failure_category == "no_marker"

def test_verifier_fallback_mode_no_evidence():
    exploit = ExploitOutput(
        vulnerability_confirmed=True,
        exploit_payload_used="print('EXPLOIT_SUCCESS')",
        sandbox_stdout="EXPLOIT_SUCCESS", # No actual evidence payload
        attempt_number=1
    )
    result = verify_exploit(exploit)
    assert result.verified is False
    assert result.failure_category == "no_evidence"

def test_verifier_hmac_mode_success():
    material = AttestationMaterial(b"key12345678901234567890123456789", b"nonce123456789012345678901234567")
    ts = str(time.time())
    token = compute_expected_hmac(material, "file_read", ts)
    
    exploit = ExploitOutput(
        vulnerability_confirmed=True,
        exploit_payload_used="cat /tmp/secret_flag.txt",
        sandbox_stdout=f"HMAC_ATTESTATION:{token}:{ts}:file_read\nFLAG{{aegis_verified_exploit}}",
        attempt_number=1
    )
    result = verify_exploit(exploit, material)
    assert result.verified is True
    
def test_verifier_hmac_mode_mismatch():
    material = AttestationMaterial(b"key12345678901234567890123456789", b"nonce123456789012345678901234567")
    ts = str(time.time())
    
    exploit = ExploitOutput(
        vulnerability_confirmed=True,
        exploit_payload_used="cat /tmp/secret_flag.txt",
        sandbox_stdout=f"HMAC_ATTESTATION:{'0'*64}:{ts}:file_read",
        attempt_number=1
    )
    result = verify_exploit(exploit, material)
    assert result.verified is False
    assert result.failure_category == "hmac_mismatch"
