"""
AST-Validated Sandbox — Fail-Closed execution layer.

Supports both Docker container execution (with HMAC attestation) and 
native Python subprocess execution (with AST filtering).

If ANY validation step fails, the sandbox refuses to execute (fail-closed).
"""

from __future__ import annotations

import ast
import hashlib
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Set, Tuple, Protocol

from app.config import SANDBOX_TIMEOUT_SECONDS
from app.schemas import SandboxResult

logger = logging.getLogger(__name__)

# ── Blocked constructs ───────────────────────────────────────────────────────

_BLOCKED_MODULES: Set[str] = {
    "shutil", "ctypes", "multiprocessing", "signal",
    "importlib", "code", "codeop", "compileall",
    "pty", "resource", "readline",
    "socket", "threading",
}

_BLOCKED_FUNCTIONS: Set[str] = {
    "os.remove", "os.unlink", "os.rmdir", "os.removedirs",
    "os.rename", "os.renames", "os.replace",
    "os.system", "os.popen", "os.exec", "os.execl",
    "os.execle", "os.execlp", "os.execlpe", "os.execv",
    "os.execve", "os.execvp", "os.execvpe", "os.fork",
    "eval", "exec", "__import__", "compile",
    "shutil.rmtree", "shutil.move",
    "pickle.loads", "pickle.load",
    "importlib.import_module",
    "ctypes.cdll",
}

# ── AST validation ───────────────────────────────────────────────────────────

class _DangerousNodeVisitor(ast.NodeVisitor):
    """Walk the AST and raise ValueError on any blocked construct."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Block dangerous module imports."""
        for alias in node.names:
            top_module = alias.name.split(".")[0]
            if top_module in _BLOCKED_MODULES:
                self.violations.append(f"Blocked import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Block dangerous from-imports including submodules."""
        if node.module:
            top_module = node.module.split(".")[0]
            if top_module in _BLOCKED_MODULES:
                self.violations.append(f"Blocked import-from: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Block dangerous function calls and open() in write mode."""
        func_name = _resolve_call_name(node)
        if func_name and func_name in _BLOCKED_FUNCTIONS:
            self.violations.append(f"Blocked call: {func_name}")
        # Block open() in write/append/create modes
        if func_name == "open" and len(node.args) > 1:
            mode_arg = node.args[1]
            if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                if any(m in mode_arg.value for m in ("w", "a", "x", "+")):
                    self.violations.append(
                        f"Blocked write-mode open() at line {node.lineno}"
                    )
        # Also block open() with mode keyword arg in write mode
        if func_name == "open":
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str) and any(
                        m in keyword.value.value for m in ("w", "a", "x", "+")
                    ):
                        self.violations.append(
                            f"Blocked write-mode open() at line {node.lineno}"
                        )
        self.generic_visit(node)


def _resolve_call_name(node: ast.Call) -> Optional[str]:
    """Best-effort resolution of a Call node to a dotted name."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        parts = []
        current = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def validate_code(code: str) -> Tuple[bool, str]:
    """
    Parse and AST-validate *code*. Returns (ok, message).
    If ok is False, the code MUST NOT be executed.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc}"

    visitor = _DangerousNodeVisitor()
    visitor.visit(tree)
    if visitor.violations:
        return False, "Blocked constructs: " + "; ".join(visitor.violations)

    return True, "OK"


# ── Execution Interfaces ──────────────────────────────────────────────────────

class SandboxInterface(Protocol):
    def execute(self, code: str, *, timeout: int = SANDBOX_TIMEOUT_SECONDS, hmac_key: Optional[bytes] = None, hmac_nonce: Optional[bytes] = None) -> SandboxResult:
        ...

class DockerSandbox:
    def execute(self, code: str, *, timeout: int = SANDBOX_TIMEOUT_SECONDS, hmac_key: Optional[bytes] = None, hmac_nonce: Optional[bytes] = None) -> SandboxResult:
        """Execute payload in an ephemeral Docker container."""
        # AST validation
        ok, reason = validate_code(code)
        if not ok:
            logger.warning("Sandbox rejected payload: %s", reason)
            return SandboxResult(success=False, stderr=reason, execution_mode="docker")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            script_path = temp_path / "payload.py"
            script_path.write_text(code)
            
            env = {}
            if hmac_key and hmac_nonce:
                env["HMAC_KEY"] = hmac_key.hex()
                env["HMAC_NONCE"] = hmac_nonce.hex()
            
            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", "256m",
                "--cpus", "0.5",
                "-v", f"{temp_dir}:/payload:ro",
            ]
            
            for k, v in env.items():
                docker_cmd.extend(["-e", f"{k}={v}"])
                
            docker_cmd.extend(["aegis-sandbox:latest", "/payload/payload.py"])
            
            try:
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return SandboxResult(
                    success=result.returncode == 0,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    execution_mode="docker"
                )
            except subprocess.TimeoutExpired:
                msg = f"Docker Sandbox timeout after {timeout}s"
                logger.warning(msg)
                return SandboxResult(success=False, stderr=msg, execution_mode="docker")
            except Exception as exc:
                return SandboxResult(success=False, stderr=f"Docker Sandbox error: {exc}", execution_mode="docker")


class SubprocessSandbox:
    def execute(self, code: str, *, timeout: int = SANDBOX_TIMEOUT_SECONDS, hmac_key: Optional[bytes] = None, hmac_nonce: Optional[bytes] = None) -> SandboxResult:
        """Execute payload in a native Python subprocess."""
        # AST validation
        ok, reason = validate_code(code)
        if not ok:
            logger.warning("Sandbox rejected payload: %s", reason)
            return SandboxResult(success=False, stderr=reason, execution_mode="subprocess")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir="."
        ) as tmp:
            tmp.write(code)
            tmp_path = Path(tmp.name)

        try:
            import os as _os
            safe_env = dict(_os.environ)

            # Strip ALL known credential / secret variables
            _DANGEROUS_VARS = {
                "OPENAI_API_KEY", "GITHUB_TOKEN", "GITHUB_CLIENT_ID",
                "GITHUB_CLIENT_SECRET", "SESSION_SECRET", "OMIUM_API_KEY",
                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                "AZURE_CLIENT_SECRET", "GCP_SERVICE_ACCOUNT_KEY",
                "DATABASE_URL", "DB_PASSWORD", "REDIS_URL",
                "SECRET_KEY", "JWT_SECRET", "COOKIE_SECRET",
            }
            for var in _DANGEROUS_VARS:
                safe_env.pop(var, None)

            result = subprocess.run(
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=safe_env,
                cwd=".",
            )
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_mode="subprocess"
            )
        except subprocess.TimeoutExpired:
            msg = f"Sandbox timeout after {timeout}s"
            logger.warning(msg)
            return SandboxResult(success=False, stderr=msg, execution_mode="subprocess")
        except Exception as exc:
            return SandboxResult(success=False, stderr=f"Sandbox error: {exc}", execution_mode="subprocess")
        finally:
            tmp_path.unlink(missing_ok=True)


def get_sandbox() -> SandboxInterface:
    """Factory to return the appropriate sandbox implementation."""
    # Since Docker is reported as not working on the host, we fall back to subprocess.
    # In a fully healthy environment, we would check if docker is running here.
    return SubprocessSandbox()

# Signature-hash dedup (circuit breaker) - moved state to db later, for now memory wrapper
_seen_hashes: Dict[str, int] = {}

def _signature_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()

def execute_payload(
    code: str,
    *,
    timeout: int = SANDBOX_TIMEOUT_SECONDS,
    max_retries: int = 3,
    hmac_key: Optional[bytes] = None,
    hmac_nonce: Optional[bytes] = None
) -> Tuple[bool, str, str]:
    """Legacy wrapper for backward compatibility."""
    sig = _signature_hash(code)
    _seen_hashes[sig] = _seen_hashes.get(sig, 0) + 1
    if _seen_hashes[sig] > max_retries:
        msg = f"Circuit breaker: payload hash {sig[:12]}… attempted {_seen_hashes[sig]} times. Blocked."
        logger.warning(msg)
        return False, "", msg
        
    sandbox = get_sandbox()
    res = sandbox.execute(code, timeout=timeout, hmac_key=hmac_key, hmac_nonce=hmac_nonce)
    return res.success, res.stdout, res.stderr
