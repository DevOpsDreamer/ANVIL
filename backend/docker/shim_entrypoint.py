"""
PID 1 Entrypoint Shim for Docker Sandbox.

Implements the sandbox-side of the HMAC attestation protocol.
Monitors for exploitation evidence and securely attests to it.
"""
import hashlib
import hmac
import os
import sys
import time
import subprocess
import threading

def _compute_hmac(key: bytes, nonce: bytes, event_type: str, timestamp: str) -> str:
    message = nonce + event_type.encode("utf-8") + timestamp.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()

def _monitor_flag(key: bytes, nonce: bytes, flag_path: str):
    """Monitor the flag file using atime polling as fallback for inotify."""
    try:
        # Wait for file to exist
        while not os.path.exists(flag_path):
            time.sleep(0.1)
        
        initial_stat = os.stat(flag_path)
        initial_atime = initial_stat.st_atime
        initial_mtime = initial_stat.st_mtime
        
        while True:
            try:
                current_stat = os.stat(flag_path)
                if current_stat.st_atime > initial_atime or current_stat.st_mtime > initial_mtime:
                    # File was accessed or modified
                    ts = str(time.time())
                    token = _compute_hmac(key, nonce, "file_read", ts)
                    print(f"HMAC_ATTESTATION:{token}:{ts}:file_read", flush=True)
                    break
            except FileNotFoundError:
                break
            time.sleep(0.1)
    except Exception as e:
        print(f"Monitor error: {e}", file=sys.stderr)

def main():
    if len(sys.argv) < 2:
        print("Usage: shim_entrypoint.py <payload_script> [args...]", file=sys.stderr)
        sys.exit(1)
        
    key_hex = os.environ.get("HMAC_KEY")
    nonce_hex = os.environ.get("HMAC_NONCE")
    
    if not key_hex or not nonce_hex:
        print("Missing HMAC_KEY or HMAC_NONCE environment variables.", file=sys.stderr)
        sys.exit(1)
        
    try:
        key = bytes.fromhex(key_hex)
        nonce = bytes.fromhex(nonce_hex)
    except ValueError:
        print("Invalid hex encoding for HMAC_KEY or HMAC_NONCE.", file=sys.stderr)
        sys.exit(1)
        
    # Clean up environment to prevent payload from reading it
    os.environ.pop("HMAC_KEY", None)
    os.environ.pop("HMAC_NONCE", None)
    
    # Create the secret flag file
    flag_path = "/tmp/secret_flag.txt"
    try:
        with open(flag_path, "w") as f:
            f.write("FLAG{aegis_verified_exploit}\n")
    except Exception as e:
        print(f"Failed to create flag file: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Start the monitor thread for standard flag
    monitor = threading.Thread(target=_monitor_flag, args=(key, nonce, flag_path), daemon=True)
    monitor.start()
    
    # Start the monitor thread for CVE dynamic proof artifact
    cve_proof_path = "/tmp/cve_proof.txt"
    monitor_cve = threading.Thread(target=_monitor_flag, args=(key, nonce, cve_proof_path), daemon=True)
    monitor_cve.start()
    
    # Run the user payload
    payload_cmd = [sys.executable] + sys.argv[1:]
    try:
        # Note: In a real environment, you might want to drop privileges here
        result = subprocess.run(payload_cmd, env=os.environ)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Failed to execute payload: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
