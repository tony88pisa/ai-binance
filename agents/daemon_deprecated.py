import time
import json
import logging
import requests
import uuid
import numpy as np
import threading
import schedule
from datetime import datetime, timezone
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

class InfoOnlyFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR

info_handler = logging.FileHandler(LOGS_DIR / "daemon.log", encoding='utf-8')
info_handler.setLevel(logging.INFO)
info_handler.addFilter(InfoOnlyFilter())

error_handler = logging.FileHandler(LOGS_DIR / "daemon_error.log", encoding='utf-8')
error_handler.setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[info_handler, error_handler]
)
logger = logging.getLogger("daemon")

from config.settings import get_settings
from storage.repository import Repository
from scheduler.session_manager import should_run_lab_cycle, should_run_live_cycle
from ai.live_brain import LiveBrain, MarketIntelligence
import ai.decision_engine as decision_engine
import ai.types as ai_types
from ai.nvidia_teacher import NvidiaTeacher
from ai.skill_generator import SkillGenerator
from ai.skill_validator import SkillValidator
from ai.promotion_gate import PromotionGate
from services.exchange_executor import ExchangeExecutor

settings = get_settings()
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
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) for i in range(1, len(closes))]
    return round(float(np.mean(trs[-period:])), 4)

def compute_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1: return 50.0
    deltas = np.diff(closes)
    ag = np.mean(np.where(deltas > 0, deltas, 0.0)[-period:])
    al = np.mean(np.where(deltas < 0, -deltas, 0.0)[-period:])
    return 100.0 if al == 0 else round(100.0 - (100.0 / (1.0 + (ag / al))), 2)

def compute_macd(closes: list, slow: int = 26, fast: int = 12, signal: int = 9) -> float:
    if len(closes) < slow: return 0.0
    arr = np.array(closes)
    macd_line = ema(arr, fast) - ema(arr, slow)
    return round(float(macd_line[-1]), 6)

def run_threaded(job_func, *args, **kwargs):
    job_thread = threading.Thread(target=job_func, args=args, kwargs=kwargs)
    job_thread.start()

def job_check_positions(repo, executor, brain):
    try:
        CURRENCY = settings.trading.stake_currency
        wallet_current = executor.get_balance(CURRENCY)
        if wallet_current <= 0:
            wallet_current = settings.trading.wallet_size
            
        controls = repo.get_supervisor_controls()
        emergency_stop = controls.get("emergency_stop", 0)
        
        # 1. Fetch Market Data & Check Exits
        current_market_states = {}
        for sym in SYMBOLS:
            try:
                k5 = fetch_data(sym, "5m")
                k1h = fetch_data(sym, "1h")
                c5 = [float(x[4]) for x in k5]
                h5 = [float(x[2]) for x in k5]
                l5 = [float(x[3]) for x in k5]
                c1h = [float(x[4]) for x in k1h]
                
                price = c5[-1]
                rsi5, rsi1h = compute_rsi(c5), compute_rsi(c1h)
                macd5, macd1h = compute_macd(c5), compute_macd(c1h)
                atr5 = compute_atr(h5, l5, c5)
                
                asset = sym.replace("USDT", "/USDT")
                intel_types_math = MarketIntelligence(asset=asset, price=price, rsi_5m=rsi5, rsi_1h=rsi1h, macd_5m=macd5, macd_1h=macd1h, atr_5m=atr5)
                intel_math = brain.evaluate(intel_types_math)
                regime = intel_math.get("regime", "UNKNOWN")
                
                snapshot = {
                    "asset": asset, "price": price, "rsi_5m": rsi5, "rsi_1h": rsi1h,
                    "macd_5m": macd5, "macd_1h": macd1h, "atr_5m": atr5,
                    "regime": regime, "decision": "hold", "confidence": 0, "consensus_score": 0,
                    "position_size_pct": 0, "atr_stop_distance": 0, "why_not_trade": ""
                }
                repo.upsert_market_snapshot(snapshot)
                current_market_states[asset] = {"price": price, "regime": regime, "intel": intel_math}
            except Exception as e:
                logger.error(f"Error fetching {sym}: {e}")
                
        # 2. Check Open Trades against Targets
        open_trades = repo.get_open_decisions()
        for trade in open_trades:
            asset = trade["asset"]
            if asset in current_market_states:
                c_data = current_market_states[asset]
                c_price = c_data["price"]
                c_regime = c_data["regime"]
                e_price = float(trade.get("entry_price", 0.0))
                atr_dist = float(trade.get("atr_stop_distance", 0.0))
                
                if e_price <= 0 or atr_dist <= 0: continue
                    
                sl_price = e_price - atr_dist
                tp_price = e_price + (atr_dist * 1.5)

                close_trade = False
                reason = ""
                
                if c_price <= sl_price:
                    close_trade, reason = True, "Stop Loss Hit"
                elif c_price >= tp_price:
                    close_trade, reason = True, "Take Profit Hit"
                elif c_regime in ["TREND_DOWN", "HIGH_VOL_CHAOS"]:
                    close_trade, reason = True, f"Defensive Exit ({c_regime})"
                    
                if close_trade:
                    pnl_pct = (c_price - e_price) / e_price
                    asset_qty = executor.get_asset_balance(asset)
                    if asset_qty <= 0:
                        asset_qty = (wallet_current * float(trade.get("size_pct", 0.1))) / e_price
                    
                    logger.info(f"[{executor.mode.upper()}] CLOSING {asset} due to {reason}.")
                    ex_sell = executor.place_market_sell(asset, asset_qty)
                    
                    repo.close_trade_with_outcome({
                        "id": f"OUT-{uuid.uuid4().hex[:8]}", "decision_id": trade["id"],
                        "realized_pnl_pct": round(pnl_pct, 4), "was_profitable": pnl_pct > 0,
                        "closed_at": datetime.now(timezone.utc).isoformat()
                    })

        # Update heartbeat
        repo.update_service_heartbeat("daemon", json.dumps({
            "mode": "LIVE_SCHEDULER", "wallet_eur": round(wallet_current, 2), "currency": CURRENCY,
            "exchange_mode": executor.mode.upper(), "supervisor_active": not emergency_stop,
            "max_trades": controls.get("max_open_trades", settings.risk.max_open_trades)
        }))
        logger.info(f"[JOB:POSITIONS] Checked {len(open_trades)} positions. Wallet: {wallet_current:.2f} {CURRENCY}")
    except Exception as e:
        logger.error(f"[JOB:POSITIONS] Error: {e}", exc_info=True)

def job_ai_analysis(repo, executor, brain):
    try:
        controls = repo.get_supervisor_controls()
        if controls.get("emergency_stop", 0):
            logger.warning("[SUPERVISOR] EMERGENCY_STOP ACTIVE. Skipping AI order placement.")
            return

        CURRENCY = settings.trading.stake_currency
        wallet_current = executor.get_balance(CURRENCY)
        max_trades = controls.get("max_open_trades", settings.risk.max_open_trades)
        min_conf = controls.get("min_confidence", settings.risk.min_confidence_buy)

        open_trades = repo.get_open_decisions()
        if len(open_trades) >= max_trades:
            return  # Capacity full

        snapshots = repo.get_latest_snapshots()
        for snap in snapshots:
            asset = snap["asset"]
            price = snap["price"]
            
            # Avoid duplicate positions
            if any(t["asset"] == asset for t in open_trades):
                continue
                
            intel_types = ai_types.MarketIntelligence(
                asset=asset, close_price=price, rsi_5m=snap.get("rsi_5m", 50.0), 
                rsi_1h=snap.get("rsi_1h", 50.0), macd_5m=snap.get("macd_5m", 0.0), 
                macd_1h=snap.get("macd_1h", 0.0), market_regime=snap.get("regime", "UNKNOWN"),
                news_count=3, research_staleness_seconds=10.0
            )
            
            ai_decision = decision_engine.evaluate(intel_types, repo)
            if ai_decision.decision.value == "buy" and ai_decision.confidence >= min_conf:
                if snap.get("regime") not in ["TREND_DOWN", "HIGH_VOL_CHAOS"]:
                    size_pct = settings.trading.default_position_size
                    pos_value = wallet_current * size_pct
                    logger.info(f"[{executor.mode.upper()}] PLACING BUY: {asset} for {pos_value:.2f}")
                    ex_order = executor.place_market_buy(asset, pos_value)
                    
                    if ex_order:
                        repo.save_trade_decision({
                            "id": f"DEC-{uuid.uuid4().hex[:8]}", "asset": asset, "action": "buy",
                            "confidence": ai_decision.confidence, "size_pct": size_pct, 
                            "thesis": ai_decision.thesis, "regime": snap.get("regime", "UNKNOWN"), 
                            "entry_price": price, "atr_stop_distance": snap.get("atr_5m", 0.0) * 1.5,
                            "status": "OPEN", "exchange_order_id": ex_order.get("orderId")
                        })
                        open_trades = repo.get_open_decisions() # Refresh list
                        if len(open_trades) >= max_trades:
                            break # Prevenire acquisto extra
        logger.info(f"[JOB:AI] AI Analysis complete. Open trades: {len(open_trades)}")
    except Exception as e:
        logger.error(f"[JOB:AI] Error: {e}", exc_info=True)

def job_lab_cycle(repo):
    try:
        logger.info("[JOB:LAB] Starting autonomous Lab cycle")
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
                
        logger.info("[JOB:LAB] Autonomous Lab cycle completed")
    except Exception as e:
        logger.error(f"[JOB:LAB] Error: {e}", exc_info=True)

def run_daemon():
    logger.info("Initializing Smart Scheduler Daemon...")
    repo = Repository()
    brain = LiveBrain()
    executor = ExchangeExecutor()

    # Schedule standard jobs
    schedule.every(10).seconds.do(run_threaded, job_check_positions, repo, executor, brain)
    schedule.every(5).minutes.do(run_threaded, job_ai_analysis, repo, executor, brain)
    
    # Run Lab Cycle automatically every hour instead of weird time windows
    schedule.every(1).hours.do(run_threaded, job_lab_cycle, repo)
    
    # Fire initial jobs so we don't have to wait 5m for the first analysis
    job_check_positions(repo, executor, brain)
    run_threaded(job_ai_analysis, repo, executor, brain)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_daemon()
