"""
TDD Tests for the AST-Validated Subprocess Sandbox.

Following the /tdd skill: vertical slices, one test at a time,
testing behavior through the public interface.
"""

from app.sandbox import validate_code, execute_payload


def test_safe_code_accepted():
    """Safe code should pass AST validation."""
    ok, msg = validate_code('print("hello world")')
    assert ok, f"Safe code rejected: {msg}"
    print("TEST 1 PASS: Safe code accepted")


def test_dangerous_import_blocked():
    """Importing blocked modules like shutil should be rejected."""
    ok, msg = validate_code('import shutil\nshutil.rmtree("/")')
    assert not ok, "Dangerous import was allowed!"
    assert "shutil" in msg
    print(f"TEST 2 PASS: Blocked: {msg}")


def test_os_remove_blocked():
    """Calling os.remove should be rejected."""
    ok, msg = validate_code('import os\nos.remove("file.txt")')
    assert not ok, "os.remove was allowed!"
    print(f"TEST 3 PASS: Blocked: {msg}")


def test_syntax_error_caught():
    """Syntax errors should fail validation fast."""
    ok, msg = validate_code("def foo(")
    assert not ok, "Syntax error was allowed!"
    assert "SyntaxError" in msg
    print(f"TEST 4 PASS: Syntax error caught: {msg}")


def test_safe_execution():
    """A safe payload should execute and return stdout."""
    success, stdout, stderr = execute_payload('print("EXPLOIT_SUCCESS")')
    assert success, f"Execution failed: {stderr}"
    assert "EXPLOIT_SUCCESS" in stdout, f"Unexpected stdout: {stdout}"
    print(f"TEST 5 PASS: Execution OK, stdout={stdout.strip()!r}")


def test_timeout_enforcement():
    """Infinite loops should be killed by the timeout."""
    code = "while True: pass"
    success, stdout, stderr = execute_payload(code, timeout=2)
    assert not success, "Infinite loop was not killed!"
    assert "timeout" in stderr.lower(), f"Unexpected stderr: {stderr}"
    print(f"TEST 6 PASS: Timeout enforced: {stderr}")


def test_subprocess_blocked():
    """Calling subprocess.run should be rejected."""
    ok, msg = validate_code('import subprocess\nsubprocess.run(["ls"])')
    assert not ok, "subprocess.run was allowed!"
    print(f"TEST 7 PASS: Blocked: {msg}")


if __name__ == "__main__":
    test_safe_code_accepted()
    test_dangerous_import_blocked()
    test_os_remove_blocked()
    test_syntax_error_caught()
    test_safe_execution()
    test_timeout_enforcement()
    test_subprocess_blocked()
    print()
    print("All sandbox tests PASSED [OK]")
