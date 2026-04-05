"""
TENGU V11.5 — BINANCE EXECUTOR (FIXED)
=========================================
Fix applicati:
  [FIX-2] Campo pnl_pct unificato (era realized_pnl_pct -> KeyError in DreamAgent).
  [FIX-P1] get_asset_balance() con fallback a 0.0 invece di crash.
  [FIX-P2] job_cleanup_stale_trades: verifica repo prima di markare EXPIRED.
  [FIX-P3] fetch_data: timeout aumentato a 8s + retry 1 volta.
  [FIX-P4] Rimosso logging.FileHandler senza delay=True (apriva file a import time).
"""
import sys
import time
import json
import logging
import requests
import uuid
import numpy as np
import schedule
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# [FIX-P4] delay=True per evitare apertura file a import-time
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EXECUTOR] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "executor.log", encoding="utf-8", delay=True),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("executor")

from config.settings import get_settings
from storage.repository import Repository
from ai.live_brain import LiveBrain, MarketIntelligence
from services.exchange_executor import ExchangeExecutor

settings = get_settings()
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


# ──────────────────────────────────────────────────────────────────
# MARKET DATA
# ──────────────────────────────────────────────────────────────────

def fetch_data(symbol: str, interval: str) -> list:
    """[FIX-P3] Timeout 8s + 1 retry."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=100"
    for attempt in range(2):
        try:
            res = requests.get(url, timeout=8)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.Timeout:
            if attempt == 0:
                logger.warning(f"Timeout fetch {symbol} {interval}, retry...")
                time.sleep(1)
            else:
                raise
    return []


def ema(data: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out = np.empty_like(data)
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
    return out


def compute_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 0.0
    trs = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, len(closes))
    ]
    return round(float(np.mean(trs[-period:])), 4)


def compute_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    ag = np.mean(np.where(deltas > 0, deltas, 0.0)[-period:])
    al = np.mean(np.where(deltas < 0, -deltas, 0.0)[-period:])
    return 100.0 if al == 0 else round(100.0 - (100.0 / (1.0 + (ag / al))), 2)


def compute_macd(closes: list, slow: int = 26, fast: int = 12, signal: int = 9) -> float:
    if len(closes) < slow:
        return 0.0
    arr = np.array(closes)
    return round(float((ema(arr, fast) - ema(arr, slow))[-1]), 6)


# ──────────────────────────────────────────────────────────────────
# JOB: CHECK POSITIONS
# ──────────────────────────────────────────────────────────────────

def job_check_positions(repo: Repository, executor: ExchangeExecutor, brain: LiveBrain) -> None:
    try:
        CURRENCY = settings.trading.stake_currency

        # [FIX-P1] get_balance con fallback
        try:
            wallet_current = executor.get_balance(CURRENCY)
            if not wallet_current or wallet_current <= 0:
                wallet_current = settings.trading.wallet_size
        except Exception as e:
            logger.warning(f"get_balance fallito: {e}. Uso wallet_size da settings.")
            wallet_current = settings.trading.wallet_size

        controls = repo.get_supervisor_controls()
        emergency_stop = controls.get("emergency_stop", 0)

        if emergency_stop:
            logger.warning("Emergency Stop attivo. Nessuna nuova operazione.")

        current_market_states = {}
        for sym in SYMBOLS:
            try:
                k5 = fetch_data(sym, "5m")
                k1h = fetch_data(sym, "1h")
                if not k5 or not k1h:
                    continue

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
                intel_math = brain.evaluate(
                    MarketIntelligence(
                        asset=asset, price=price,
                        rsi_5m=rsi5, rsi_1h=rsi1h,
                        macd_5m=macd5, macd_1h=macd1h,
                        atr_5m=atr5,
                    )
                )
                regime = intel_math.get("regime", "UNKNOWN")

                repo.upsert_market_snapshot({
                    "asset": asset, "price": price,
                    "rsi_5m": rsi5, "rsi_1h": rsi1h,
                    "macd_5m": macd5, "macd_1h": macd1h,
                    "atr_5m": atr5, "regime": regime,
                    "decision": "hold", "confidence": 0,
                    "consensus_score": 0, "position_size_pct": 0,
                    "atr_stop_distance": 0, "why_not_trade": "",
                })
                current_market_states[asset] = {"price": price, "regime": regime}

            except Exception as e:
                logger.error(f"Error fetching {sym}: {e}")

        # ── Position Management ────────────────────────────────────────────
        open_trades = repo.get_open_decisions()
        for trade in open_trades:
            asset = trade["asset"]
            if asset not in current_market_states:
                continue

            c_data = current_market_states[asset]
            c_price = c_data["price"]
            c_regime = c_data["regime"]
            e_price = float(trade.get("entry_price", 0.0))
            atr_dist = float(trade.get("atr_stop_distance", 0.0))

            if e_price <= 0 or atr_dist <= 0:
                continue

            sl_price = e_price - atr_dist
            tp_price = e_price + (atr_dist * 1.5)

            close_trade, reason = False, ""
            if c_price <= sl_price:
                close_trade, reason = True, "Stop Loss Hit"
            elif c_price >= tp_price:
                close_trade, reason = True, "Take Profit Hit"
            elif c_regime in ["TREND_DOWN", "HIGH_VOL_CHAOS"]:
                close_trade, reason = True, f"Defensive Exit ({c_regime})"

            if close_trade:
                pnl_pct = (c_price - e_price) / e_price

                # [FIX-P1] get_asset_balance con fallback
                try:
                    asset_qty = executor.get_asset_balance(asset)
                    if not asset_qty or asset_qty <= 0:
                        asset_qty = (wallet_current * float(trade.get("size_pct", 0.1))) / e_price
                except Exception:
                    asset_qty = (wallet_current * float(trade.get("size_pct", 0.1))) / e_price

                repo.log_activity(
                    "executor", "SELL",
                    f"{asset} closing: {reason} | PnL: {round(pnl_pct * 100, 2)}%"
                )
                logger.info(f"[{executor.mode.upper()}] Closing {asset} due to {reason}.")
                repo.update_decision_status(trade["id"], "CLOSING")
                executor.place_market_sell(asset, asset_qty)

                # [FIX-2] Campo standardizzato: pnl_pct (non realized_pnl_pct)
                repo.close_trade_with_outcome({
                    "id": f"OUT-{uuid.uuid4().hex[:8]}",
                    "decision_id": trade["id"],
                    "pnl_pct": round(pnl_pct, 4),           # campo unificato
                    "was_profitable": pnl_pct > 0,
                    "exit_reason": reason,
                    "closed_at": datetime.now(timezone.utc).isoformat(),
                })

        # ── Heartbeat ────────────────────────────────────────────────────────
repo.update_service_heartbeat(
    "executor",
    json.dumps({
        "mode": "LIVE_EXECUTOR",
        "wallet_eur": round(wallet_current, 2),
        "currency": CURRENCY,
        "exchange_mode": executor.mode.upper(),
        "supervisor_active": not emergency_stop,
        "max_trades": controls.get("max_open_trades", settings.risk.max_open_trades),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }),
)
repo.log_activity(
    "executor", "CYCLE",
    f"Checked {len(open_trades)} positions. Wallet: {wallet_current:.2f} {CURRENCY}"
)
logger.info(f"Execution run complete. Wallet: {wallet_current:.2f} {CURRENCY} | Positions: {len(open_trades)}")

    except Exception as e:
        logger.error(f"Executor Error: {e}", exc_info=True)


# ──────────────────────────────────────────────────────────────────
# JOB: CLEANUP STALE TRADES [FIX-P2]
# ──────────────────────────────────────────────────────────────────

def job_cleanup_stale_trades(repo: Repository, executor: ExchangeExecutor) -> None:
    """[FIX-P2] Marca come EXPIRED i trade aperti da >24h senza balance attivo."""
    try:
        logger.info("Running stale trade cleanup...")
        stale_trades = repo.get_stale_decisions(max_age_hours=24)
        if not stale_trades:
            logger.info("Nessun trade stale trovato.")
            return

        for trade in stale_trades:
            asset = trade["asset"]
            try:
                balance = executor.get_asset_balance(asset)
            except Exception as e:
                logger.warning(f"get_asset_balance({asset}) fallito: {e}. Skip.")
                continue

            if balance is None or balance <= 0:
                logger.warning(
                    f"Trade {trade['id']} per {asset} stale (>24h) senza balance. Marcato EXPIRED."
                )
                repo.update_decision_status(trade["id"], "EXPIRED")
                repo.log_activity(
                    "executor", "EXPIRED",
                    f"{asset} trade {trade['id']} marcato EXPIRED (stale, no balance)."
                )
            else:
                logger.info(
                    f"Trade {trade['id']} per {asset} e' vecchio ma ha balance ({balance:.6f}). Mantenuto."
                )

    except Exception as e:
        logger.error(f"Cleanup Error: {e}", exc_info=True)


# ──────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("TENGU V11.5 Binance Executor starting...")
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
