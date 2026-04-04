import os
import json
import logging
import requests
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ai.openrouter")

FREE_MODELS = [
    "qwen/qwen3.6-plus:free",
    "stepfun/step-3.5-flash:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free"
]

def get_openrouter_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return key

def call_openrouter(messages: List[Dict[str, str]], model: str, timeout: int = 30) -> Optional[str]:
    """Call an individual OpenRouter model."""
    key = get_openrouter_key()
    if not key:
        return None
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://github.com/TenguHQ",
        "X-Title": "Tengu V10 Autonomous Trader",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3
    }
    
    try:
        # Rate limit safety delay for concurrent threads
        time.sleep(1.0)
        
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        
        # Gestione esplicta dei limiti gratuiti per evitare ban
        if resp.status_code == 429:
            logger.warning(f"[{model}] RATE LIMIT (429) raggiunto sui modelli gratuiti. Blocco di sicurezza attivo.")
            return None
            
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter block/error on {model}. Rate limit or network issue: {e}")
    except Exception as e:
        logger.error(f"OpenRouter unhandled error on {model}: {e}")
        
    return None

def call_swarm_consensus(messages: List[Dict[str, str]], max_models: int = 3, timeout: int = 25) -> Dict[str, Any]:
    """
    Intersroga i migliori N modelli gratuiti in parallelo.
    Ritorna un dizionario con i responsi raw. L'engine parent valuterà il consensus.
    """
    import concurrent.futures
    
    results = {}
    models_to_use = FREE_MODELS[:max_models]
    
    if not get_openrouter_key():
        logger.warning("No OPENROUTER_API_KEY found. Swarm skipped.")
        return results
        
    def fetch(m):
        return m, call_openrouter(messages, m, timeout=timeout)
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_models) as executor:
        futures = [executor.submit(fetch, m) for m in models_to_use]
        for f in concurrent.futures.as_completed(futures):
            try:
                m, res = f.result()
                if res is not None:
                    results[m] = res
            except Exception as e:
                logger.error(f"Swarm thread error: {e}")
                
    return results
