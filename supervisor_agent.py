import time
import json
import logging
import requests
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# Logging setup
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOGS_DIR / "supervisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SUPERVISOR] %(message)s",
    handlers=[logging.FileHandler(log_path, encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("supervisor")

from storage.repository import Repository

def get_market_context(repo: Repository):
    state = repo.get_service_state("daemon")
    try: sj = json.loads(state.get("state_json", "{}"))
    except: sj = {}
    
    wallet = sj.get("wallet_eur", 50.0)
    open_trades = repo.get_open_decisions()
    history = repo.get_history() # I need to check if get_history exists or just query
    
    # Simple winrate calc
    with repo._conn() as conn:
        outcomes = conn.execute("SELECT * FROM trade_outcomes ORDER BY closed_at DESC LIMIT 20").fetchall()
        outcomes = [dict(o) for o in outcomes]
        wins = sum(1 for o in outcomes if o['was_profitable'])
        winrate = (wins / len(outcomes) * 100) if outcomes else 0
        
    return {
        "wallet_eur": wallet,
        "pnl_pct": ((wallet - 50.0) / 50.0) * 100,
        "open_count": len(open_trades),
        "winrate_recent": winrate,
        "recent_outcomes": outcomes[:10],
        "open_trades": [{"asset": t["asset"], "pnl": t.get("pnl_pct", 0)} for t in open_trades]
    }

def call_ai_supervisor(context: dict):
    api_key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
    # Standard NVIDIA NIM endpoint
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    
    prompt = f"""
    You are the AI Supervisor for a crypto trading bot. 
    Current State:
    {json.dumps(context, indent=2)}
    
    Mission: Protect CAPITAL. The bot's budget is 50.00 EUR.
    
    Rules for output:
    1. emergency_stop: SET TO 1 ONLY if the wallet is below 46.00 EUR. 
       If the wallet is >= 46.00 EUR, ALWAYS set emergency_stop to 0 (resume), even in TREND_DOWN.
    2. min_confidence: Regulate between 72 and 78.
    3. Return ONLY a JSON object.
    
    Fields: 
       - assessment: string (narrative evaluation of current PnL vs Regime)
       - emergency_stop: boolean (0: resume, 1: halt)
       - max_open_trades: integer (3)
       - min_confidence: integer (72-78)
       - close_losers_threshold: float (-5.0 to -2.0)
       - actions: string (brief command)
    """
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1024
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        resp_json = res.json()
        ai_msg = resp_json['choices'][0]['message']['content']
        # Extract JSON from potential markdown blocks
        if "```json" in ai_msg:
            ai_msg = ai_msg.split("```json")[1].split("```")[0]
        elif "```" in ai_msg:
             ai_msg = ai_msg.split("```")[1].split("```")[0]
        
        return json.loads(ai_msg.strip())
    except Exception as e:
        logger.error(f"AI Call failed: {e}")
        return None

def run_supervisor():
    repo = Repository()
    logger.info("AI Supervisor started.")
    
    while True:
        try:
            context = get_market_context(repo)
            logger.info(f"Analyzing state... Wallet: {context['wallet_eur']:.2f} EUR")
            
            advice = call_ai_supervisor(context)
            if advice:
                logger.info(f"AI Assessment: {advice['assessment']}")
                
                # Rule: emergency_stop=1 ONLY if wallet < 46
                wallet = context.get('wallet_eur', 50.0)
                e_stop = 1 if (advice.get("emergency_stop") and wallet < 46.0) else 0
                
                # Rule: min_confidence 72-78
                raw_conf = advice.get("min_confidence", 75)
                final_conf = max(72, min(raw_conf, 78))
                
                repo.update_supervisor_controls({
                    "emergency_stop": e_stop,
                    "max_open_trades": 3,
                    "min_confidence": final_conf,
                    "close_losers_threshold": advice.get("close_losers_threshold", -5.0),
                    "ai_reasoning": advice.get("assessment", "")
                })
                # Log to DB
                repo.add_supervisor_log(
                    wallet_state=f"{wallet:.2f} EUR",
                    assessment=advice.get("assessment", ""),
                    actions=f"Update: stop={e_stop}, conf={final_conf}"
                )
            else:
                logger.warning("No advice from AI. Maintaining current state.")
                current_controls = repo.get_supervisor_controls()
                repo.update_supervisor_controls({
                    "emergency_stop": current_controls.get("emergency_stop", 0),
                    "max_open_trades": current_controls.get("max_open_trades", 3),
                    "min_confidence": min(current_controls.get("min_confidence", 75), 75),
                    "ai_reasoning": "AI NVIDIA unavailable - fallback activated. Lowering min_confidence to 75% max."
                })
                
        except Exception as e:
            logger.error(f"Supervisor loop error: {e}")
            
        time.sleep(300) # 5 minutes

if __name__ == "__main__":
    run_supervisor()
