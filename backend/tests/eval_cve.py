"""
CVE Evaluation Harness.

Runs statistical trials (N=10) of the AEGIS pipeline against real-world
vulnerable Docker containers (e.g., Log4Shell, Spring4Shell).
Collects Exploit Success Rate (ESR), False Positive Rate (FPR),
and execution latency.
"""

import argparse
import json
import logging
import os
import time
import requests
import subprocess
from pathlib import Path

# Need to make sure backend app is in pythonpath
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.schemas import ReconOutput, ExploitOutput, VulnerableEndpoint, HttpMethod
from app.agents.exploiter import run_exploit
from app.agents.recon_universal import run_universal_recon

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_cve")

TARGETS = {
    "cve-2021-44228": {
        "image": "ghcr.io/christophetd/log4shell-vulnerable-app",
        "port": 8080,
        "repo_url": "https://github.com/christophetd/log4shell-vulnerable-app",
        "name": "Log4Shell"
    }
}

def start_container(target_id: str) -> str:
    """Start the target docker container and return its ID."""
    cfg = TARGETS[target_id]
    logger.info(f"Starting {cfg['name']} container from {cfg['image']}...")
    cmd = [
        "docker", "run", "-d", "-p", f"{cfg['port']}:8080", 
        "--name", f"aegis_eval_{target_id}", cfg['image']
    ]
    try:
        # Cleanup any existing
        subprocess.run(["docker", "rm", "-f", f"aegis_eval_{target_id}"], capture_output=True)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        container_id = result.stdout.strip()
        logger.info(f"Container started: {container_id}")
        
        # Wait for it to be ready
        time.sleep(10)
        return container_id
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start container: {e.stderr}")
        raise

def stop_container(target_id: str):
    """Stop the target docker container."""
    logger.info(f"Stopping container aegis_eval_{target_id}...")
    subprocess.run(["docker", "rm", "-f", f"aegis_eval_{target_id}"], capture_output=True)

def run_trial(target_id: str, trial_num: int) -> dict:
    """Run a single AEGIS pipeline trial against the target."""
    cfg = TARGETS[target_id]
    target_url = f"http://127.0.0.1:{cfg['port']}"
    
    start_time = time.time()
    
    # We mock the clone directory for the trial
    clone_dir = f"/tmp/aegis_eval_clone_{trial_num}"
    
    try:
        logger.info(f"--- Trial {trial_num}: Recon ---")
        recon = run_universal_recon(cfg["repo_url"], clone_dir=clone_dir)
        
        logger.info(f"--- Trial {trial_num}: Exploit ---")
        # Override target URL for local docker container testing
        recon.target_url = target_url
        exploit = run_exploit(recon)
        
        latency = time.time() - start_time
        return {
            "trial": trial_num,
            "success": exploit.vulnerability_confirmed,
            "latency": latency,
            "error": None
        }
    except Exception as e:
        logger.error(f"Trial {trial_num} failed: {e}")
        return {
            "trial": trial_num,
            "success": False,
            "latency": time.time() - start_time,
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description="Evaluate AEGIS on Real CVEs")
    parser.add_argument("--target", type=str, default="cve-2021-44228", help="Target CVE to evaluate")
    parser.add_argument("--trials", type=int, default=10, help="Number of trials to run")
    args = parser.parse_args()

    if args.target not in TARGETS:
        logger.error(f"Unknown target: {args.target}")
        sys.exit(1)

    target_cfg = TARGETS[args.target]
    results = []
    
    try:
        start_container(args.target)
        for i in range(1, args.trials + 1):
            logger.info(f"=== Starting Trial {i}/{args.trials} ===")
            res = run_trial(args.target, i)
            results.append(res)
            logger.info(f"Trial {i} result: {res}")
            # Small delay between trials
            time.sleep(2)
    finally:
        stop_container(args.target)

    # Calculate metrics
    successes = sum(1 for r in results if r["success"])
    esr = successes / args.trials
    avg_latency = sum(r["latency"] for r in results) / args.trials

    report = {
        "target": args.target,
        "name": target_cfg["name"],
        "trials": args.trials,
        "esr": esr,
        "avg_latency_seconds": avg_latency,
        "raw_results": results
    }

    os.makedirs("results", exist_ok=True)
    out_file = f"results/eval_{args.target}.json"
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"Evaluation complete! ESR: {esr*100}%, Avg Latency: {avg_latency:.2f}s")
    logger.info(f"Results saved to {out_file}")

if __name__ == "__main__":
    main()
