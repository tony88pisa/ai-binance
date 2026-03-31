import time
import json
import logging
import requests
import uuid
import numpy as np
from datetime import datetime, timezone
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

daemon_log_path = LOGS_DIR / "daemon.log"
daemon_err_path = LOGS_DIR / "daemon_error.log"

class InfoOnlyFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR

info_handler = logging.FileHandler(daemon_log_path, encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_handler.addFilter(InfoOnlyFilter())

error_handler = logging.FileHandler(daemon_err_path, encoding='utf-8')
error_handler.setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[info_handler, error_handler]
)
logger = logging.getLogger("daemon")

from storage.repository import Repository
from scheduler.session_manager import should_run_lab_cycle, should_run_live_cycle
from ai.live_brain import LiveBrain, MarketIntelligence
from ai.nvidia_teacher import NvidiaTeacher
from ai.skill_generator import SkillGenerator
from ai.skill_validator import SkillValidator
from ai.promotion_gate import PromotionGate

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

def fetch_data(symbol: str, interval: str) -> list:
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=100"
    res = requests.get(url, timeout=5)
    res.raise_for_status()
    return res.json()

def ema(data: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out = np.empty_like(data)
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
    return out

def compute_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    if len(closes) < period + 1: return 0.0
    trs = []
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        pc = closes[i-1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return round(float(np.mean(trs[-period:])), 4)

def compute_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1: return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    ag = np.mean(gains[-period:])
    al = np.mean(losses[-period:])
    if al == 0: return 100.0
    return round(100.0 - (100.0 / (1.0 + (ag / al))), 2)

def compute_macd(closes: list) -> float:
    if len(closes) < 26: return 0.0
    arr = np.array(closes, dtype=float)
    return round(float(ema(arr, 12)[-1] - ema(arr, 26)[-1]), 6)

def run_daemon():
    repo = Repository()
    brain = LiveBrain()
    lab_run_today = False
    
    # Inizializza Wallet Progressivo (Testnet Locale)
    DEFAULT_BUDGET = 50.0
    MAX_OPEN_TRADES = 3
    
    while True:
        try:
            # Recupera stato precedente per wallet
            state = repo.get_service_state("daemon")
            state_data = {}
            if state and state.get("state_json"):
                try: state_data = json.loads(state["state_json"])
                except: pass
            
            wallet_eur = state_data.get("wallet_eur", DEFAULT_BUDGET)
            
            # --- SUPERVISOR OVERRIDES ---
            controls = repo.get_supervisor_controls()
            emergency_stop = controls.get("emergency_stop", 0)
            max_trades = controls.get("max_open_trades", MAX_OPEN_TRADES)
            min_conf = controls.get("min_confidence", 70)
            
            is_live = should_run_live_cycle()
            is_lab = should_run_lab_cycle()
            mode_str = "LIVE_MODE" if is_live else ("LAB_MODE" if is_lab else "IDLE")
            
            # Update heartbeat con wallet corrente e stato supervisor
            repo.update_service_heartbeat("daemon", json.dumps({
                "mode": mode_str, 
                "wallet_eur": round(wallet_eur, 2),
                "supervisor_active": not emergency_stop,
                "max_trades": max_trades
            }))

            if is_live:
                lab_run_today = False

                # CHECK EMERGENCY — salta tutto il ciclo live se attivo
                if emergency_stop:
                    logger.warning("[SUPERVISOR] EMERGENCY_STOP ACTIVE. Skipping cycle.")
                    time.sleep(30)
                    continue

                current_market_states = {}
                for sym in SYMBOLS:
                    k5 = fetch_data(sym, "5m")
                    k1h = fetch_data(sym, "1h")
                    
                    c5 = [float(x[4]) for x in k5]
                    h5 = [float(x[2]) for x in k5]
                    l5 = [float(x[3]) for x in k5]
                    c1h = [float(x[4]) for x in k1h]
                    
                    price = c5[-1]
                    rsi5 = compute_rsi(c5)
                    rsi1h = compute_rsi(c1h)
                    macd5 = compute_macd(c5)
                    macd1h = compute_macd(c1h)
                    atr5 = compute_atr(h5, l5, c5)

                    asset = sym.replace("USDT", "/USDT")
                    intel = MarketIntelligence(asset, price, rsi5, rsi1h, macd5, macd1h, atr5)
                    
                    # 1. Calcoli matematici e di regime da LiveBrain
                    live_decision = brain.evaluate(intel)
                    
                    # 3. Interroga Ollama (Decision Engine) usando il tipo corretto
                    import ai.types as ai_types
                    intel_types = ai_types.MarketIntelligence(
                        asset=asset,
                        close_price=price,
                        rsi_5m=rsi5,
                        rsi_1h=rsi1h,
                        macd_5m=macd5,
                        macd_1h=macd1h,
                        market_regime=live_decision["regime"]
                    )
                    
                    import ai.decision_engine as decision_engine
                    ai_decision = decision_engine.evaluate(intel_types, repo)
                    
                    # 4. Merge dei dati o Fallback
                    if "model_unreachable" in ai_decision.risk_flags:
                        decision = live_decision
                    else:
                        decision = {
                            "decision": ai_decision.decision.value,
                            "confidence": ai_decision.confidence,
                            "regime": live_decision["regime"],
                            "consensus_score": live_decision["consensus_score"],
                            "position_size_pct": live_decision["position_size_pct"],
                            "atr_stop_distance": live_decision["atr_stop_distance"],
                            "thesis": ai_decision.thesis,
                            "technical_basis": ai_decision.technical_basis,
                            "risk_flags": ai_decision.risk_flags,
                            "why_not_trade": ""
                        }
                    
                    current_market_states[asset] = {"price": price, "regime": decision["regime"]}

                    snapshot = {
                        "asset": asset, "price": price, "rsi_5m": rsi5, "rsi_1h": rsi1h,
                        "macd_5m": macd5, "macd_1h": macd1h, "atr_5m": atr5,
                        **decision
                    }
                    repo.upsert_market_snapshot(snapshot)
                    
                    if decision["decision"] == "buy":
                        # --- RISK CONTROLS ---
                        open_trades = repo.get_open_decisions()
                        if len(open_trades) >= max_trades:
                            # Prevenzione per eccesso posizioni
                            continue
                            
                        # Prevenzione duplicati asset
                        if any(t["asset"] == asset for t in open_trades):
                            continue
                            
                        # Blocco TREND_DOWN o HIGH_VOL_CHAOS
                        if decision["regime"] in ["TREND_DOWN", "HIGH_VOL_CHAOS"]:
                            continue
                        
                        # Soglia Minima Confidence (Supervisor)
                        if decision["confidence"] < min_conf:
                            continue

                        # --- EMERGENCY WALLET STOP ---
                        if wallet_eur < 35.0:
                            logger.warning(f"[RISK] Wallet below safety threshold 35.0 (Current: {wallet_eur:.2f}). Blocking BUY on {asset}.")
                            continue
                        
                        # Calcolo size in EUR basata su wallet progressivo
                        size_pct = decision["position_size_pct"]
                        pos_value_eur = wallet_eur * size_pct
                        
                        repo.save_trade_decision({
                            "id": f"DEC-{uuid.uuid4().hex[:8]}",
                            "asset": asset,
                            "action": decision["decision"],
                            "confidence": decision["confidence"],
                            "size_pct": size_pct,
                            "thesis": decision["thesis"] + f" | Wallet Context: {wallet_eur:.2f} EUR",
                            "regime": decision["regime"],
                            "entry_price": price,
                            "atr_stop_distance": decision["atr_stop_distance"],
                            "status": "OPEN"
                        })
                        logger.info(f"[LIVE] BUY entry on {asset} @ {price}. Pos Size: {pos_value_eur:.2f} EUR")

                logger.info(f"[LIVE] Cycle complete. Wallet: {wallet_eur:.2f} EUR. Synced {len(SYMBOLS)} assets.")

                # Risoluzione Outcome (chiude ordini maturi o stoppati in modo atomico)
                open_trades = repo.get_open_decisions()
                for trade in open_trades:
                    asset = trade["asset"]
                    if asset not in current_market_states:
                        continue
                    
                    c_price = current_market_states[asset]["price"]
                    c_regime = current_market_states[asset]["regime"]
                    e_price = float(trade.get("entry_price", 0.0))
                    atr_dist = float(trade.get("atr_stop_distance", 0.0))
                    t_size_pct = float(trade.get("size_pct", 0.0))
                    
                    if e_price <= 0 or atr_dist <= 0:
                        continue
                        
                    sl_price = e_price - atr_dist
                    tp_price = e_price + (atr_dist * 1.5) # Take Profit a 1.5R

                    close_trade = False
                    reason = ""
                    
                    if c_price <= sl_price:
                        close_trade = True
                        reason = "Stop Loss Hit"
                    elif c_price >= tp_price:
                        close_trade = True
                        reason = "Take Profit Hit"
                    elif c_regime in ["TREND_DOWN", "HIGH_VOL_CHAOS"]:
                        close_trade = True
                        reason = f"Defensive Exit ({c_regime})"

                    if close_trade:
                        pnl_pct = (c_price - e_price) / e_price
                        
                        # Calcolo impatto sul wallet (progressivo)
                        # Nota: wallet_eur in questo momento è quello caricato ad inizio ciclo.
                        trade_profit_eur = wallet_eur * t_size_pct * pnl_pct
                        wallet_eur += trade_profit_eur
                        
                        outcome = {
                            "id": f"OUT-{uuid.uuid4().hex[:8]}",
                            "decision_id": trade["id"],
                            "realized_pnl_pct": round(pnl_pct, 4),
                            "was_profitable": pnl_pct > 0
                        }
                        
                        # Aggiornamento wallet in state_json per persistenza
                        state_data["wallet_eur"] = round(wallet_eur, 2)
                        repo.update_service_heartbeat("daemon", json.dumps(state_data))

                        # Riferimento alla repository per atomicità outcome-chiusura in mutua elusione db duplication
                        repo.close_trade_with_outcome(outcome)
                        logger.info(f"[OUTCOME] Closed {asset} due to {reason}. PnL: {pnl_pct*100:.2f}%. Wallet now: {wallet_eur:.2f} EUR")

            elif is_lab and not lab_run_today:
                logger.info("[LAB] Starting lab cycle")
                teacher = NvidiaTeacher(repo)
                generator = SkillGenerator()
                validator = SkillValidator(repo)
                gate = PromotionGate(repo)

                analysis = teacher.analyze()
                candidates = generator.generate_from_findings(analysis)
                
                for cand in candidates:
                    repo.save_skill_candidate(cand)
                    val = validator.validate(cand)
                    repo.save_skill_validation(cand["skill_id"], val)
                    if gate.evaluate(cand["skill_id"], val):
                        repo.save_skill_promotion(cand["skill_id"], "Automatic Promotion via Gate")
                        
                lab_run_today = True
                logger.info("[LAB] Lab cycle completed")

            time.sleep(30)

        except Exception as e:
            logger.error(f"Daemon error: {e}", exc_info=True)
            time.sleep(30)

if __name__ == "__main__":
    run_daemon()
