"""
TENGU V11.5 — RISK CONTROLLER (FIXED)
========================================
Fix applicati:
  [FIX-6] Rimosso doppio import / doppio logging setup.
  [FIX-7] Rimosso repo.get_history() non verificato (sostituito con query diretta).
  [FIX-8] emergency_stop logic corretta: soglia 10% sul budget iniziale fisso.
  [FIX-9] tax_reserve inizializzata a 0 anche nel branch else (NameError fix).
  [FIX-10] Supermemory import isolato — startup non crasha se lib mancante.
"""
import sys
import time
import json
import logging
import os
import threading
import requests
from datetime import datetime, timezone
from pathlib import Path

import schedule
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from config.settings import get_settings
from storage.repository import Repository
from ai.mcp_client import MCPClient

settings = get_settings()

# ── Logging (una sola volta) [FIX-6] ─────────────────────────────────
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONTROLLER] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "controller.log", encoding="utf-8", delay=True),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("controller")

# ── Supermemory (optional) [FIX-10] ───────────────────────────────
try:
    from supermemory import Supermemory as _Supermemory
    _SUPERMEMORY_LIB_AVAILABLE = True
except ImportError:
    _Supermemory = None
    _SUPERMEMORY_LIB_AVAILABLE = False
    logger.info("Libreria supermemory non installata — memoria semantica disabilitata.")

CRYPTO_TAX_RATE = 0.33  # Tassazione crypto italiana 2026

# ──────────────────────────────────────────────────────────────────
# CONTEXT BUILDER [FIX-7]
# ──────────────────────────────────────────────────────────────────

def get_market_context(repo: Repository) -> dict:
    """Costruisce il contesto di mercato per l'AI Supervisor."""
    state = repo.get_service_state("daemon")
    try:
        sj = json.loads(state.get("state_json", "{}"))
    except (json.JSONDecodeError, AttributeError):
        sj = {}

    initial_budget = settings.trading.wallet_size
    currency = settings.trading.stake_currency
    wallet_value = sj.get("wallet_eur", initial_budget)
    open_trades = repo.get_open_decisions()

    # [FIX-7] Query diretta — non si usa piu' get_history()
    try:
        with repo._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trade_outcomes ORDER BY closed_at DESC LIMIT 20"
            ).fetchall()
            outcomes = [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Errore lettura trade_outcomes: {e}")
        outcomes = []

    wins = sum(1 for o in outcomes if o.get("was_profitable", False))
    winrate = (wins / len(outcomes) * 100) if outcomes else 0.0

    return {
        "wallet": wallet_value,
        "initial_budget": initial_budget,
        "currency": currency,
        "pnl_pct": ((wallet_value - initial_budget) / initial_budget) * 100,
        "open_count": len(open_trades),
        "winrate_recent": round(winrate, 2),
        "recent_outcomes": [
            {k: o[k] for k in ("asset", "pnl_pct", "was_profitable", "closed_at") if k in o}
            for o in outcomes[:10]
        ],
        "open_trades": [
            {"asset": t.get("asset", "?"), "pnl": t.get("pnl_pct", 0)} for t in open_trades
        ],
        "macro_regime": MCPClient().fetch_macro_regime(),
    }


# ──────────────────────────────────────────────────────────────────
# AI SUPERVISOR CALL
# ──────────────────────────────────────────────────────────────────

def call_ai_supervisor(context: dict, risk_policy: str = "") -> dict | None:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        logger.warning("NVIDIA_API_KEY non trovata — skip AI Supervisor.")
        return None

    model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
    url = "https://integrate.api.nvidia.com/v1/chat/completions"

    # [FIX-8] Soglia emergenza sul budget iniziale fisso, non sul wallet corrente
    emergency_threshold = context["initial_budget"] * 0.90

    prompt = f"""You are the AI Supervisor for a crypto trading bot.
Current State:
{json.dumps(context, indent=2)}

--- LONG-TERM RISK POLICY & LEARNINGS ---
{risk_policy or "No historical policy stored yet."}
---

Mission: PROTECT CAPITAL.
Initial budget: {context["initial_budget"]:.2f} {context["currency"]}
Emergency threshold (10% loss): {emergency_threshold:.2f} {context["currency"]}

Rules:
1. emergency_stop = 1 ONLY IF wallet < {emergency_threshold:.2f} OR macro_regime = "RISK-OFF".
   If wallet >= threshold AND macro OK -> ALWAYS set emergency_stop = 0.
2. min_confidence: between 68 and 75. Use 68-70 for testnet exploration.
3. Return ONLY a valid JSON object. No markdown, no code blocks.

Output fields:
  assessment (string): narrative evaluation
  emergency_stop (int): 0 or 1
  max_open_trades (int): 1-3
  min_confidence (int): 68-75
  close_losers_threshold (float): -5.0 to -2.0
  actions (string): brief command
  new_insights (array of strings): learnings to persist (empty array if none)
"""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        t0 = time.time()
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        resp_json = res.json()
        duration_ms = int((time.time() - t0) * 1000)
        ai_msg = resp_json["choices"][0]["message"]["content"]

        try:
            from telemetry.cost_tracker import get_cost_tracker
            tracker = get_cost_tracker(str(PROJECT_ROOT))
            usage = resp_json.get("usage", {})
            tracker.record_call(
                model=model, caller="risk_controller",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                duration_ms=duration_ms, success=True,
            )
        except Exception:
            pass

        if "```json" in ai_msg:
            ai_msg = ai_msg.split("```json")[1].split("```")[0]
        elif "```" in ai_msg:
            ai_msg = ai_msg.split("```")[1].split("```")[0]

        return json.loads(ai_msg.strip())

    except Exception as e:
        logger.error(f"AI Supervisor call failed: {e}")
        try:
            from telemetry.cost_tracker import get_cost_tracker
            tracker = get_cost_tracker(str(PROJECT_ROOT))
            tracker.record_call(model=model, caller="risk_controller", duration_ms=0, success=False, error=str(e))
        except Exception:
            pass
        return None


# ──────────────────────────────────────────────────────────────────
# SUPERMEMORY HELPERS
# ──────────────────────────────────────────────────────────────────

def _build_supermemory_client():
    if not _SUPERMEMORY_LIB_AVAILABLE:
        return None
    sm_key = os.getenv("SUPERMEMORY_API_KEY", "").strip()
    if not sm_key:
        logger.warning("SUPERMEMORY_API_KEY non trovata — bypass semantico.")
        return None
    try:
        return _Supermemory(api_key=sm_key)
    except Exception as e:
        logger.error(f"Errore init Supermemory: {e}")
        return None


def _fetch_risk_policy(sm_client) -> str:
    if not sm_client:
        return ""
    try:
        resp = sm_client.search.memories(q="Global historical risk policy and emergency insights", limit=2)
        if resp and hasattr(resp, "data"):
            return " ".join(r.memory for r in resp.data if hasattr(r, "memory"))
        if isinstance(resp, dict) and "data" in resp:
            return " ".join(r.get("memory", "") for r in resp["data"])
    except Exception as e:
        logger.warning(f"Errore ricerca Supermemory: {e}")
    return ""


def _persist_insights(sm_client, insights: list) -> None:
    for insight in insights:
        payload = f"RISK_INSIGHT: {insight}"
        if sm_client:
            try:
                sm_client.add(content=payload)
                logger.info(f"Insight salvato in Supermemory: {insight[:60]}...")
            except Exception as e:
                logger.warning(f"Supermemory.add failed: {e}")
        else:
            logger.info(f"(Simulated Supermemory) Insight: {insight[:60]}...")


# ──────────────────────────────────────────────────────────────────
# JOB SUPERVISE
# ──────────────────────────────────────────────────────────────────

def job_supervise(repo: Repository) -> None:
    """Ciclo supervisione: fetch contesto -> AI decision -> applica controlli."""
    try:
        sm_client = _build_supermemory_client()
        risk_policy = _fetch_risk_policy(sm_client)

        context = get_market_context(repo)
        logger.info(
            f"Analyzing state... Wallet: {context['wallet']:.2f} {context['currency']} | "
            f"WR recente: {context['winrate_recent']:.1f}% | "
            f"Trade aperti: {context['open_count']} | "
            f"Macro: {context['macro_regime']}"
        )

        advice = call_ai_supervisor(context, risk_policy)

        initial_capital = settings.trading.wallet_size
        wallet = context["wallet"]
        currency = context["currency"]

        # ── Tax-Aware Auto-Compounding ─────────────────────────────────────
        # [FIX-9] tax_reserve inizializzato SEMPRE prima del branch
        tax_reserve = 0.0
        position_size_usdt = wallet * settings.trading.default_position_size

        if settings.trading.auto_compound:
            gross_profit = max(0.0, wallet - initial_capital)
            tax_reserve = round(gross_profit * CRYPTO_TAX_RATE, 4)
            net_equity = wallet - tax_reserve

            if net_equity >= settings.trading.global_take_profit:
                logger.warning(
                    f"GLOBAL TP RAGGIUNTO (net_equity={net_equity:.2f} >= "
                    f"{settings.trading.global_take_profit:.2f}). Modalita' conservativa (5%)."
                )
                position_size_usdt = net_equity * 0.05
            else:
                position_size_usdt = net_equity * settings.trading.risk_per_trade_pct

            logger.info(
                f"Compound | Wallet={wallet:.2f} | Profit lordo={gross_profit:.2f} | "
                f"Riserva fiscale 33%={tax_reserve:.2f} | Net equity={net_equity:.2f} | "
                f"Position size={position_size_usdt:.2f}"
            )

        if advice:
            logger.info(f"AI NVIDIA Assessment: {advice.get('assessment', 'N/A')}")

            _persist_insights(sm_client, advice.get("new_insights", []))

            # [FIX-8] emergency_stop: soglia fissa sul budget iniziale
            emergency_threshold = initial_capital * 0.90
            raw_stop = advice.get("emergency_stop", 0)
            e_stop = 1 if (raw_stop and wallet <= emergency_threshold) else 0

            raw_conf = advice.get("min_confidence", 70)
            final_conf = max(68, min(raw_conf, 75))

            repo.update_supervisor_controls({
                "emergency_stop": e_stop,
                "max_open_trades": min(advice.get("max_open_trades", 2), 3),
                "min_confidence": final_conf,
                "close_losers_threshold": advice.get("close_losers_threshold", -3.0),
                "max_leverage": 10,
                "position_size_usdt": round(position_size_usdt, 2),
                "tax_reserve_usdt": tax_reserve,
                "ai_reasoning": advice.get("assessment", ""),
            })
            repo.add_supervisor_log(
                wallet_state=f"{wallet:.2f} {currency}",
                assessment=advice.get("assessment", ""),
                actions=f"stop={e_stop}, conf={final_conf}, size={position_size_usdt:.2f}",
            )
        else:
            logger.warning("AI non disponibile — mantengo stato precedente con confidence ridotta.")
            current = repo.get_supervisor_controls()
            repo.update_supervisor_controls({
                "emergency_stop": current.get("emergency_stop", 0),
                "max_open_trades": current.get("max_open_trades", 2),
                "min_confidence": min(current.get("min_confidence", 70), 70),
                "ai_reasoning": "AI NVIDIA non disponibile — fallback attivato.",
            })

        repo.update_service_heartbeat("risk_controller", json.dumps({
            "status": "completed",
            "wallet": wallet,
            "tax_reserve": tax_reserve,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    except Exception as e:
        logger.error(f"[JOB:SUPERVISE] Error: {e}", exc_info=True)


def _run_threaded(job_func, *args, **kwargs) -> None:
    threading.Thread(target=job_func, args=args, kwargs=kwargs, daemon=True).start()


def run_supervisor() -> None:
    repo = Repository()
    logger.info("AI Risk Controller V11.5 Starting")
    schedule.every(5).minutes.do(_run_threaded, job_supervise, repo)
    job_supervise(repo)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_supervisor()
