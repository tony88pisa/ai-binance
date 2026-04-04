import time
import json
import logging
import requests
import uuid
import numpy as np
import schedule
from datetime import datetime, timezone
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EXECUTOR] %(message)s",
                    handlers=[logging.FileHandler(LOGS_DIR / "executor.log", encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger("executor")

from config.settings import get_settings
from storage.repository import Repository
from ai.live_brain import LiveBrain, MarketIntelligence
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
    return round(float((ema(arr, fast) - ema(arr, slow))[-1]), 6)

def job_check_positions(repo, executor, brain):
    try:
        CURRENCY = settings.trading.stake_currency
        wallet_current = executor.get_balance(CURRENCY)
        if wallet_current <= 0: wallet_current = settings.trading.wallet_size
            
        controls = repo.get_supervisor_controls()
        emergency_stop = controls.get("emergency_stop", 0)
        
        current_market_states = {}
        for sym in SYMBOLS:
            try:
                k5 = fetch_data(sym, "5m"); k1h = fetch_data(sym, "1h")
                c5, h5, l5 = [float(x[4]) for x in k5], [float(x[2]) for x in k5], [float(x[3]) for x in k5]
                c1h = [float(x[4]) for x in k1h]
                
                price = c5[-1]
                rsi5, rsi1h = compute_rsi(c5), compute_rsi(c1h)
                macd5, macd1h = compute_macd(c5), compute_macd(c1h)
                atr5 = compute_atr(h5, l5, c5)
                
                asset = sym.replace("USDT", "/USDT")
                intel_math = brain.evaluate(MarketIntelligence(asset=asset, price=price, rsi_5m=rsi5, rsi_1h=rsi1h, macd_5m=macd5, macd_1h=macd1h, atr_5m=atr5))
                regime = intel_math.get("regime", "UNKNOWN")
                
                repo.upsert_market_snapshot({
                    "asset": asset, "price": price, "rsi_5m": rsi5, "rsi_1h": rsi1h,
                    "macd_5m": macd5, "macd_1h": macd1h, "atr_5m": atr5,
                    "regime": regime, "decision": "hold", "confidence": 0, "consensus_score": 0,
                    "position_size_pct": 0, "atr_stop_distance": 0, "why_not_trade": ""
                })
                current_market_states[asset] = {"price": price, "regime": regime}
            except Exception as e:
                logger.error(f"Error fetching {sym}: {e}")
                
        open_trades = repo.get_open_decisions()
        for trade in open_trades:
            asset = trade["asset"]
            if asset in current_market_states:
                c_data = current_market_states[asset]
                c_price, c_regime = c_data["price"], c_data["regime"]
                e_price = float(trade.get("entry_price", 0.0))
                atr_dist = float(trade.get("atr_stop_distance", 0.0))
                
                if e_price <= 0 or atr_dist <= 0: continue
                sl_price, tp_price = e_price - atr_dist, e_price + (atr_dist * 1.5)

                close_trade, reason = False, ""
                if c_price <= sl_price: close_trade, reason = True, "Stop Loss Hit"
                elif c_price >= tp_price: close_trade, reason = True, "Take Profit Hit"
                elif c_regime in ["TREND_DOWN", "HIGH_VOL_CHAOS"]: close_trade, reason = True, f"Defensive Exit ({c_regime})"
                    
                if close_trade:
                    pnl_pct = (c_price - e_price) / e_price
                    asset_qty = executor.get_asset_balance(asset)
                    if asset_qty <= 0: asset_qty = (wallet_current * float(trade.get("size_pct", 0.1))) / e_price
                    
                    logger.info(f"[{executor.mode.upper()}] Transitioning {asset} to CLOSING due to {reason}.")
                    repo.update_decision_status(trade["id"], "CLOSING")
                    
                    logger.info(f"[{executor.mode.upper()}] Executing Market Sell for {asset}.")
                    executor.place_market_sell(asset, asset_qty)
                    
                    repo.close_trade_with_outcome({
                        "id": f"OUT-{uuid.uuid4().hex[:8]}", "decision_id": trade["id"],
                        "realized_pnl_pct": round(pnl_pct, 4), "was_profitable": pnl_pct > 0,
                        "closed_at": datetime.now(timezone.utc).isoformat()
                    })

        repo.update_service_heartbeat("executor", json.dumps({
            "mode": "LIVE_EXECUTOR", "wallet_eur": round(wallet_current, 2), "currency": CURRENCY,
            "exchange_mode": executor.mode.upper(), "supervisor_active": not emergency_stop,
            "max_trades": controls.get("max_open_trades", settings.risk.max_open_trades)
        }))
        logger.info(f"Execution run complete. Checked {len(open_trades)} positions. Wallet: {wallet_current:.2f} {CURRENCY}")
    except Exception as e:
        logger.error(f"Executor Error: {e}", exc_info=True)

def job_cleanup_stale_trades(repo, executor):
    """Checks for trades that have been stuck in OPEN/CLOSING for >24h and verifies them."""
    try:
        logger.info("Running stale trade cleanup cycle...")
        stale_trades = repo.get_stale_decisions(max_age_hours=24)
        for trade in stale_trades:
            asset = trade["asset"]
            balance = executor.get_asset_balance(asset)
            if balance <= 0:
                logger.warning(f"Trade {trade['id']} for {asset} is stale (age > 24h) and no balance found. Marking as EXPIRED.")
                repo.update_decision_status(trade["id"], "EXPIRED")
            else:
                logger.info(f"Trade {trade['id']} for {asset} is old but still has active balance. Carrying forward.")
    except Exception as e:
        logger.error(f"Cleanup Error: {e}")

if __name__ == "__main__":
    logger.info("Starting Binance Executor Agent...")
    repo = Repository()
    brain = LiveBrain()
    executor = ExchangeExecutor()
    
    schedule.every(10).seconds.do(job_check_positions, repo, executor, brain)
    schedule.every(6).hours.do(job_cleanup_stale_trades, repo, executor)
    
    job_check_positions(repo, executor, brain)
    job_cleanup_stale_trades(repo, executor)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
