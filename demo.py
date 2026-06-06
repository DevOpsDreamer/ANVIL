import argparse
import sys
import logging
import asyncio
from backend.app.pipeline import run_scan
from backend.app.schemas import MasterState

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("demo")

async def run_demo(args):
    logger.info("Starting AEGIS/ANVIL Demonstration")
    logger.info("Target URL: %s", args.url)
    logger.info("Deterministic Mode: %s", args.deterministic_only)
    
    if args.deterministic_only:
        # Mock OpenAI API key so LLM calls immediately fail and trigger the deterministic fallback
        import os
        os.environ["OPENAI_API_KEY"] = "mock-key-to-force-fallback"
        logger.info("OPENAI_API_KEY overwritten to force deterministic fallback.")

    logger.info("Running pipeline...")
    try:
        import uuid
        scan_id = str(uuid.uuid4())
        await run_scan(scan_id=scan_id, token="demo-token", repo_url=args.url, base_branch="main")
        logger.info("Pipeline finished!")
        
    except Exception as e:
        logger.error("Demo failed: %s", e)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="AEGIS/ANVIL Demo Script")
    parser.add_argument("--url", default="https://github.com/DevOpsDreamer/Anvil-Test-Target", help="Target URL to scan")
    parser.add_argument("--deterministic-only", action="store_true", help="Force agents to use only deterministic fallback mode (disable LLM)")
    args = parser.parse_args()
    
    asyncio.run(run_demo(args))

if __name__ == "__main__":
    main()
