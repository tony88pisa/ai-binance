import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def test_openrouter():
    logging.info("--- TESTING OPENROUTER SWARM ---")
    from ai.openrouter_client import call_swarm_consensus, get_openrouter_key
    
    key = get_openrouter_key()
    if not key:
        logging.error("❌ OPENROUTER_API_KEY NOT FOUND in .env")
        return False
        
    logging.info(f"API Key found: {key[:6]}...{key[-4:]}")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'Swarm Online' if you can read this."}
    ]
    
    # Test just 1 model to be quick and avoid limits
    results = call_swarm_consensus(messages, max_models=1, timeout=20)
    
    if results:
        for model, resp in results.items():
            logging.info(f"✅ OpenRouter [{model}] Response: {resp.strip()}")
        return True
    else:
        logging.error("❌ OpenRouter Swarm failed to return a response.")
        return False

def test_supermemory():
    logging.info("\n--- TESTING SUPERMEMORY ---")
    from supermemory import Supermemory
    
    key = os.getenv("SUPERMEMORY_API_KEY")
    if not key:
        logging.error("❌ SUPERMEMORY_API_KEY NOT FOUND in .env")
        return False
        
    logging.info(f"API Key found: {key[:6]}...{key[-4:]}")
    
    try:
        sm = Supermemory(api_key=key)
        # Try a simple search
        resp = sm.search.memories(q="trading", limit=1)
        logging.info("✅ Supermemory Connection OK (Method accessible).")
        # In case it's a 401, the library usually raises or the check cycle will show it
        return True
    except Exception as e:
        logging.error(f"❌ Supermemory call failed: {e}")
        return False

if __name__ == "__main__":
    or_ok = test_openrouter()
    sm_ok = test_supermemory()
    
    if or_ok and sm_ok:
        logging.info("\n🟢 ALL SYSTEMS LIVE! The keys are working.")
        sys.exit(0)
    else:
        logging.error("\n🔴 SOME SYSTEMS FAILED. Check the errors above.")
        sys.exit(1)
