import argparse
import sys
import logging
import asyncio
import os
import subprocess
import time
import requests
import json
from sseclient import SSEClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("demo")

def start_target_app():
    logger.info("Starting target_app/vulnerable_server.py on port 9999...")
    target_process = subprocess.Popen(
        [sys.executable, "target_app/vulnerable_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2) # Give it time to start
    return target_process

def trigger_scan(backend_url, repo_url, token):
    logger.info(f"Triggering scan for {repo_url}...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"repo_url": repo_url, "base_branch": "main"}
    
    resp = requests.post(f"{backend_url}/api/scan", json=payload, headers=headers)
    if resp.status_code != 202:
        logger.error(f"Failed to start scan: {resp.text}")
        sys.exit(1)
        
    data = resp.json()
    scan_id = data["scan_id"]
    stream_url = f"{backend_url}{data['stream_url']}"
    logger.info(f"Scan started with ID {scan_id}. Streaming progress...")
    return scan_id, stream_url

def poll_sse_stream(stream_url):
    logger.info(f"Connecting to SSE stream: {stream_url}")
    response = requests.get(stream_url, stream=True, headers={'Accept': 'text/event-stream'})
    client = SSEClient(response)
    
    for event in client.events():
        if event.event == 'keepalive':
            continue
            
        data = json.loads(event.data)
        logger.info(f"[{event.event.upper()}] {data.get('message', '')}")
        
        if event.event in ('completed', 'failed'):
            logger.info("Scan finished.")
            if event.event == 'completed':
                logger.info(f"PR URL: {data.get('pr_url', 'None')}")
            break

def main():
    parser = argparse.ArgumentParser(description="AEGIS/ANVIL Demo Script")
    parser.add_argument("--repo", default="https://github.com/DevOpsDreamer/Anvil-Test-Target", help="Target URL to scan")
    parser.add_argument("--backend", default="http://localhost:8000", help="Backend URL")
    parser.add_argument("--token", default="test-token", help="Auth token for backend")
    args = parser.parse_args()
    
    target_process = None
    try:
        target_process = start_target_app()
        scan_id, stream_url = trigger_scan(args.backend, args.repo, args.token)
        poll_sse_stream(stream_url)
    except KeyboardInterrupt:
        logger.info("Aborted by user.")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
    finally:
        if target_process:
            logger.info("Stopping target_app...")
            target_process.terminate()
            target_process.wait()

if __name__ == "__main__":
    main()
