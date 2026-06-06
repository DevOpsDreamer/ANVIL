import pytest
from app.sandbox import get_sandbox, SubprocessSandbox, validate_code

def test_ast_validation_safe_code():
    code = "x = 1 + 1\nprint(x)"
    ok, msg = validate_code(code)
    assert ok is True

def test_ast_validation_blocked_import():
    code = "import shutil\nshutil.rmtree('/')"
    ok, msg = validate_code(code)
    assert ok is False
    assert "Blocked import" in msg

def test_ast_validation_blocked_call():
    code = "import os\nos.system('echo hacked')"
    ok, msg = validate_code(code)
    assert ok is False
    assert "Blocked call: os.system" in msg

def test_subprocess_sandbox_success():
    sandbox = SubprocessSandbox()
    code = "print('Hello, secure world!')"
    result = sandbox.execute(code)
    assert result.success is True
    assert "Hello, secure world!" in result.stdout

def test_subprocess_sandbox_timeout():
    sandbox = SubprocessSandbox()
    # An infinite loop to test timeout
    code = "import time\nwhile True: time.sleep(0.1)"
    result = sandbox.execute(code, timeout=1)
    assert result.success is False
    assert "timeout" in result.stderr.lower()
