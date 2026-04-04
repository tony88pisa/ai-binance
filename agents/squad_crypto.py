import time
import json
import logging
import uuid
import requests
import numpy as np
import schedule
from datetime import datetime, timezone
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SQUAD_CRYPTO] %(message)s",
                    handlers=[logging.FileHandler(LOGS_DIR / "squad_crypto.log", encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger("squad_crypto")

from config.settings import get_settings
from storage.repository import Repository
import ai.types as ai_types
import ai.decision_engine as decision_engine
from services.exchange_executor import ExchangeExecutor

settings = get_settings()

# Universo crypto gestito da questa squadra
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

def fetch_candles(symbol: str, interval: str) -> list:
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=100"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    return res.json()

def compute_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1: return 50.0
    deltas = np.diff(closes)
    ag = np.mean(np.where(deltas > 0, deltas, 0.0)[-period:])
    al = np.mean(np.where(deltas < 0, -deltas, 0.0)[-period:])
    return 100.0 if al == 0 else round(100.0 - (100.0 / (1.0 + (ag / al))), 2)

def compute_macd(closes: list) -> float:
    if len(closes) < 26: return 0.0
    arr = np.array(closes)
    alpha_f, alpha_s = 2.0 / 13, 2.0 / 27
    ema_f, ema_s = np.empty_like(arr), np.empty_like(arr)
    ema_f[0] = ema_s[0] = arr[0]
    for i in range(1, len(arr)):
        ema_f[i] = alpha_f * arr[i] + (1 - alpha_f) * ema_f[i - 1]
        ema_s[i] = alpha_s * arr[i] + (1 - alpha_s) * ema_s[i - 1]
    return round(float((ema_f - ema_s)[-1]), 6)

def compute_atr(highs, lows, closes, period=14) -> float:
    if len(closes) < period + 1: return 0.0
    trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, len(closes))]
    return round(float(np.mean(trs[-period:])), 4)

def job_crypto_cycle(repo, executor):
    """Ciclo completo: Fetch dati -> Analisi AI -> Decisione -> Esecuzione."""
    cycle_start = time.time()
    try:
        controls = repo.get_supervisor_controls()
        if controls.get("emergency_stop", 0):
            logger.warning("⛔ EMERGENCY_STOP ACTIVE. Ciclo saltato.")
            repo.log_activity("squad_crypto", "BLOCKED", "Emergency stop attivo")
            return

        CURRENCY = settings.trading.stake_currency
        wallet_current = executor.get_balance(CURRENCY)
        max_trades = controls.get("max_open_trades", settings.risk.max_open_trades)
        min_conf = controls.get("min_confidence", settings.risk.min_confidence_buy)
        open_trades = repo.get_open_decisions()

        analyzed = 0
        signals = 0

        for sym in CRYPTO_SYMBOLS:
            asset = sym.replace("USDT", "/USDT")
            try:
                # 1. FETCH DATI LIVE DA BINANCE
                k5 = fetch_candles(sym, "5m")
                k1h = fetch_candles(sym, "1h")
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
                
                # 2. ANALISI AI (Ollama/Gemma)
                if any(t["asset"] == asset for t in open_trades):
                    # Aggiorna snapshot ma non analizzare per buy
                    repo.upsert_market_snapshot({
                        "asset": asset, "price": price, "rsi_5m": rsi5, "rsi_1h": rsi1h,
                        "macd_5m": macd5, "macd_1h": macd1h, "atr_5m": atr5,
                        "regime": "MONITORING", "decision": "hold", "confidence": 0,
                        "consensus_score": 0, "position_size_pct": 0,
                        "atr_stop_distance": 0, "why_not_trade": "Position already open"
                    })
                    continue
                
                intel = ai_types.MarketIntelligence(
                    asset=asset, close_price=price, rsi_5m=rsi5, rsi_1h=rsi1h,
                    macd_5m=macd5, macd_1h=macd1h, market_regime="UNKNOWN",
                    news_count=3, research_staleness_seconds=10.0
                )
                
                ai_decision = decision_engine.evaluate(intel, repo)
                analyzed += 1
                
                # 3. SALVA SNAPSHOT AGGIORNATO
                regime = "TREND_UP" if macd5 > 0 and rsi5 > 50 else "TREND_DOWN" if macd5 < 0 and rsi5 < 40 else "RANGING"
                repo.upsert_market_snapshot({
                    "asset": asset, "price": price, "rsi_5m": rsi5, "rsi_1h": rsi1h,
                    "macd_5m": macd5, "macd_1h": macd1h, "atr_5m": atr5,
                    "decision": ai_decision.decision.value, "confidence": ai_decision.confidence,
                    "regime": regime, "consensus_score": ai_decision.confidence / 100.0,
                    "position_size_pct": 0.0, "atr_stop_distance": atr5 * 1.5,
                    "why_not_trade": ai_decision.thesis
                })
                
                logger.info(f"📊 {asset} ${price:,.2f} | RSI={rsi5:.0f} MACD={macd5:.4f} | {ai_decision.decision.value.upper()} conf={ai_decision.confidence}% | {ai_decision.thesis}")
                
                # 4. ESECUZIONE SE BUY
                if ai_decision.decision.value == "buy" and ai_decision.confidence >= min_conf:
                    if regime not in ["TREND_DOWN"] and len(open_trades) < max_trades:
                        signals += 1
                        size_pct = settings.trading.default_position_size
                        pos_value = wallet_current * size_pct
                        logger.info(f"🟢 PLACING BUY: {asset} for {pos_value:.2f} {CURRENCY}")
                        ex_order = executor.place_market_buy(asset, pos_value)
                        
                        if ex_order:
                            repo.save_trade_decision({
                                "id": f"DEC-CRYPTO-{uuid.uuid4().hex[:8]}", "asset": asset, "action": "buy",
                                "confidence": ai_decision.confidence, "size_pct": size_pct,
                                "thesis": ai_decision.thesis, "regime": regime,
                                "entry_price": price, "atr_stop_distance": atr5 * 1.5,
                                "status": "OPEN", "inner_monologue": ai_decision.inner_monologue,
                                "agent_name": "Squad-Crypto", "exchange_order_id": ex_order.get("orderId")
                            })
                            repo.log_activity("squad_crypto", "BUY", f"{asset} @ ${price:,.2f} | Conf: {ai_decision.confidence}%")
                            
            except Exception as e:
                logger.error(f"Errore su {sym}: {e}")

        elapsed = round(time.time() - cycle_start, 1)
        repo.update_service_heartbeat("squad_crypto", json.dumps({
            "mode": "ACTIVE", "last_run": datetime.now(timezone.utc).isoformat(),
            "analyzed": analyzed, "signals": signals, "elapsed_s": elapsed
        }))
        repo.log_activity("squad_crypto", "CYCLE", f"Analizzati {analyzed} asset in {elapsed}s | Segnali: {signals}")
        logger.info(f"✅ Ciclo completato in {elapsed}s — {analyzed} analizzati, {signals} segnali")
    except Exception as e:
        logger.error(f"ERRORE CRITICO: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("🚀 Squad Crypto Agent (Binance 24/7) avviato!")
    repo = Repository()
    executor = ExchangeExecutor()
    
    # Ciclo ogni 60 secondi per dati live reali
    schedule.every(60).seconds.do(job_crypto_cycle, repo, executor)
    job_crypto_cycle(repo, executor)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
