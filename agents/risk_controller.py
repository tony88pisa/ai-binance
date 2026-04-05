import time
import json
import logging
import requests
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration setup
from config.settings import get_settings
settings = get_settings()
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# Logging setup
# Logging setup
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOGS_DIR / "controller.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONTROLLER] %(message)s",
    handlers=[logging.FileHandler(log_path, encoding='utf-8', delay=True), logging.StreamHandler()]
)
logger = logging.getLogger("controller")

from storage.repository import Repository
from ai.mcp_client import MCPClient

def get_market_context(repo: Repository):
    state = repo.get_service_state("daemon")
    try: sj = json.loads(state.get("state_json", "{}"))
    except: sj = {}
    
    initial_budget = settings.trading.wallet_size
    currency = settings.trading.stake_currency
    wallet = sj.get("wallet_eur", initial_budget)
    open_trades = repo.get_open_decisions()
    history = repo.get_history() # I need to check if get_history exists or just query
    
    # Simple winrate calc
    with repo._conn() as conn:
        outcomes = conn.execute("SELECT * FROM trade_outcomes ORDER BY closed_at DESC LIMIT 20").fetchall()
        outcomes = [dict(o) for o in outcomes]
        wins = sum(1 for o in outcomes if o['was_profitable'])
        winrate = (wins / len(outcomes) * 100) if outcomes else 0
        
    return {
        "wallet": wallet,
        "currency": currency,
        "pnl_pct": ((wallet - initial_budget) / initial_budget) * 100,
        "open_count": len(open_trades),
        "winrate_recent": winrate,
        "recent_outcomes": outcomes[:10],
        "open_trades": [{"asset": t["asset"], "pnl": t.get("pnl_pct", 0)} for t in open_trades],
        "macro_regime": MCPClient().fetch_macro_regime()
    }

def call_ai_supervisor(context: dict, risk_policy: str = ""):
    api_key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    
    prompt = f"""
    You are the AI Supervisor for a crypto trading bot. 
    Current State:
    {json.dumps(context, indent=2)}
    
    --- LONG-TERM RISK POLICY & LEARNINGS ---
    {risk_policy}
    -----------------------------------------

    
    Mission: Protect CAPITAL. The bot's initial budget is {context['wallet']} {context['currency']}.
    
    Rules for output:
    1. emergency_stop: SET TO 1 ONLY if the wallet is below {context['wallet'] * 0.90} {context['currency']} (10% loss) OR if Macro System Regime is "RISK-OFF". 
       If the wallet is above this threshold AND Macro is OK, ALWAYS set emergency_stop to 0 (resume).
    2. min_confidence: Regulate between 68 and 75. Lower values (68-70) are encouraged in TESTNET for exploration.
    3. Return ONLY a JSON object.
    
    Fields: 
       - assessment: string (narrative evaluation of current PnL vs Regime)
       - emergency_stop: boolean (0: resume, 1: halt)
       - max_open_trades: integer (3)
       - min_confidence: integer (72-78)
       - close_losers_threshold: float (-5.0 to -2.0)
       - actions: string (brief command)
       - new_insights: array of strings (Important learnings or new risk rules to append to long-term memory, empty if none)
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
        t_start = time.time()
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        resp_json = res.json()
        duration_ms = int((time.time() - t_start) * 1000)
        ai_msg = resp_json['choices'][0]['message']['content']
        
        # Track cost
        try:
            from telemetry.cost_tracker import get_cost_tracker
            tracker = get_cost_tracker(str(PROJECT_ROOT))
            usage = resp_json.get("usage", {})
            tracker.record_call(
                model=model, caller="risk_controller",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                duration_ms=duration_ms, success=True
            )
        except Exception:
            pass
        
        # Extract JSON from potential markdown blocks
        if "```json" in ai_msg:
            ai_msg = ai_msg.split("```json")[1].split("```")[0]
        elif "```" in ai_msg:
             ai_msg = ai_msg.split("```")[1].split("```")[0]
        
        return json.loads(ai_msg.strip())
    except Exception as e:
        logger.error(f"AI Call failed: {e}")
        # Track failed call
        try:
            from telemetry.cost_tracker import get_cost_tracker
            tracker = get_cost_tracker(str(PROJECT_ROOT))
            tracker.record_call(
                model=model, caller="risk_controller",
                duration_ms=0, success=False, error=str(e)
            )
        except Exception:
            pass
        return None

import threading
import schedule

def job_supervise(repo):
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
        
        from config.settings import get_settings
        settings = get_settings()
        
        sm_key = os.getenv("SUPERMEMORY_API_KEY", "").strip()
        if not sm_key:
            logger.warning("SUPERMEMORY_API_KEY non trovata. Bypass semantico.")
            sm_client = None
        else:
            try:
                from supermemory import Supermemory
                sm_client = Supermemory(api_key=sm_key)
            except Exception as e:
                logger.error(f"Errore caricamento Supermemory library: {e}")
                sm_client = None
                
        risk_policy = ""
        if sm_client:
            try:
                # Recupera policy generale con retry
                resp = sm_client.search.memories(q="Global historical risk policy and emergency insights", limit=2)
                if resp and hasattr(resp, 'data'):
                    risk_policy = " ".join([r.memory for r in resp.data if hasattr(r, 'memory')])
                elif isinstance(resp, dict) and "data" in resp:
                    risk_policy = " ".join([r.get("memory", "") for r in resp["data"]])
            except Exception as e:
                logger.warning(f"Errore durante la ricerca semantica (Supermemory): {e}. Procedo con contesto base.")
        
        context = get_market_context(repo)
        logger.info(f"Analyzing state... Wallet: {context['wallet']:.2f} {context['currency']}")
        
        advice = call_ai_supervisor(context, risk_policy)
        if advice:
            logger.info(f"AI NVIDIA Assessment: {advice['assessment']}")
            
            # Save new insights to Supermemory
            new_insights = advice.get("new_insights", [])
            for insight in new_insights:
                insight_str = f"RISK_INSIGHT: {insight}"
                if sm_client:
                    sm_client.add(content=insight_str)
                    logger.info(f"Appended new insight to Supermemory: {insight}")
                else:
                    logger.info(f"(Simulated) Appended new insight: {insight}")
            
            initial_budget = settings.trading.wallet_size
            emergency_limit = initial_budget * 0.90
            wallet = context.get('wallet', initial_budget)
            currency = context.get('currency', 'USDT')
            
            e_stop = 1 if (advice.get("emergency_stop") and wallet < emergency_limit) else 0
            raw_conf = advice.get("min_confidence", 70)
            final_conf = max(68, min(raw_conf, 75))
            
            repo.update_supervisor_controls({
                "emergency_stop": e_stop, "max_open_trades": 3, "min_confidence": final_conf,
                "close_losers_threshold": advice.get("close_losers_threshold", -5.0),
                "ai_reasoning": advice.get("assessment", "")
            })
            repo.add_supervisor_log(
                wallet_state=f"{wallet:.2f} {currency}", assessment=advice.get("assessment", ""),
                actions=f"Update: stop={e_stop}, conf={final_conf}"
            )
        else:
            logger.warning("No advice from AI. Maintaining current state.")
            current_controls = repo.get_supervisor_controls()
            repo.update_supervisor_controls({
                "emergency_stop": current_controls.get("emergency_stop", 0),
                "max_open_trades": current_controls.get("max_open_trades", 3),
                "min_confidence": min(current_controls.get("min_confidence", 70), 70),
                "ai_reasoning": "AI NVIDIA unavailable - fallback activated. Lowering min_confidence to 70%."
            })
    except Exception as e:
        logger.error(f"[JOB:SUPERVISE] Error: {e}", exc_info=True)

def run_threaded(job_func, *args, **kwargs):
    threading.Thread(target=job_func, args=args, kwargs=kwargs).start()

def run_supervisor():
    repo = Repository()
    logger.info("AI Supervisor (Scheduled) started.")
    
    schedule.every(5).minutes.do(run_threaded, job_supervise, repo)
    job_supervise(repo) # initial run
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_supervisor()
