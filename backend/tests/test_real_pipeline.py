import pytest
import time
import os
from unittest.mock import patch, MagicMock

from app.schemas import MasterState, PlaceName, WebhookPayload
from app.graph import build_web_cpn
from app.hmac_shim import generate_attestation_material, compute_expected_hmac

def test_full_pipeline_hmac_verification():
    # 1. Setup mock functions to intercept agent calls
    
    # We will simulate a clean run where recon finds a vulnerability,
    # exploit successfully exploits it and prints the HMAC token,
    # verifier verifies the token, and patcher generates a patch.
    
    # Mock recon
    recon_mock = MagicMock()
    recon_mock.vulnerable_endpoints = [MagicMock(injection_vector="SQL Injection")]
    
    # Mock exploit to return the proper HMAC token
    material = generate_attestation_material()
    ts = str(time.time())
    token = compute_expected_hmac(material, "sql_injection", ts)
    stdout = f"HMAC_ATTESTATION:{token}:{ts}:sql_injection\nFLAG{{aegis_verified_exploit}}"
    
    exploit_mock = MagicMock()
    exploit_mock.vulnerability_confirmed = True
    exploit_mock.exploit_payload_used = "' OR 1=1--"
    exploit_mock.sandbox_stdout = stdout
    exploit_mock.attempt_number = 1
    
    # Mock verification
    verify_mock = MagicMock()
    verify_mock.verified = True
    
    # Mock patch
    patch_mock = MagicMock()
    patch_mock.pr_url = "https://github.com/DevOpsDreamer/ANVIL/pull/1"
    
    # We need to test the CPN routing based on these
    # Instead of actually calling the real agents, we mock the transition actions 
    # or the underlying functions they call.
    
    with patch("app.agents.recon.run_recon_source", return_value=recon_mock), \
         patch("app.agents.exploiter.run_exploit", return_value=exploit_mock), \
         patch("app.agents.verifier.verify_exploit", return_value=verify_mock), \
         patch("app.agents.patcher.run_patch_github", return_value=patch_mock):
         
        # Create initial state
        state = MasterState(
            trace_id="test-trace-1",
            task_id="test-task-1",
            current_node=PlaceName.PRECON_PENDING.value,
            repo_url="https://github.com/DevOpsDreamer/ANVIL",
            repo_dir="/tmp/dummy",
            webhook=WebhookPayload(
                target_url="https://github.com/DevOpsDreamer/ANVIL",
                deployment_id="test",
                repo_url="https://github.com/DevOpsDreamer/ANVIL",
                repo_name="DevOpsDreamer/ANVIL",
                github_token="dummy",
                base_branch="main"
            ),
            github_token="dummy",
            base_branch="main"
        )
        
        # Build CPN
        engine = build_web_cpn("test-scan-1", emit_fn=MagicMock(), loop=MagicMock())
        
        # Run CPN
        final_state = engine.run(state)
        
        # Assertions
        assert final_state.completed is True
        assert final_state.current_node == PlaceName.PPATCH_DONE.value
        assert final_state.error is None
        assert final_state.patch is not None
        assert final_state.patch.pr_url == "https://github.com/DevOpsDreamer/ANVIL/pull/1"

def test_pipeline_hmac_failure_retry():
    # Test that an HMAC mismatch causes a retry in the verification loop
    recon_mock = MagicMock()
    recon_mock.vulnerable_endpoints = [MagicMock(injection_vector="SQL Injection")]
    
    # Exploit prints BAD hmac
    exploit_mock = MagicMock()
    exploit_mock.vulnerability_confirmed = True
    exploit_mock.exploit_payload_used = "' OR 1=1--"
    exploit_mock.sandbox_stdout = "HMAC_ATTESTATION:badtoken:123:sql_injection"
    exploit_mock.attempt_number = 1
    
    verify_mock = MagicMock()
    verify_mock.verified = False
    verify_mock.reason = "HMAC attestation failed"
    
    with patch("app.agents.recon.run_recon_source", return_value=recon_mock), \
         patch("app.agents.exploiter.run_exploit", return_value=exploit_mock), \
         patch("app.agents.verifier.verify_exploit", return_value=verify_mock):
         
        state = MasterState(
            trace_id="test-trace-2",
            task_id="test-task-2",
            current_node=PlaceName.PRECON_PENDING.value,
            repo_url="https://github.com/DevOpsDreamer/ANVIL",
            repo_dir="/tmp/dummy",
            webhook=WebhookPayload(
                target_url="https://github.com/DevOpsDreamer/ANVIL",
                deployment_id="test",
                repo_url="https://github.com/DevOpsDreamer/ANVIL",
                repo_name="DevOpsDreamer/ANVIL",
                github_token="dummy",
                base_branch="main"
            ),
            github_token="dummy",
            base_branch="main"
        )
        
        engine = build_web_cpn("test-scan-2", emit_fn=MagicMock(), loop=MagicMock())
        
        # Set max steps to prevent infinite loop just in case
        engine.MAX_STEPS = 20
        final_state = engine.run(state)
        
        # Should exhaust retries and end up in PERROR
        assert final_state.completed is True
        assert final_state.current_node == PlaceName.PERROR.value
        assert "failed after 3 retries" in final_state.error
        assert final_state.retry_count == 3
