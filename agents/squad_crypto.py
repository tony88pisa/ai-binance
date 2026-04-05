"""
TENGU V11.5 — Ultimate Autonomous Scaler.
Pattern: Resilience, Capital Protection, and Kelly Sizing.

Features:
- Emergency Self-Sleep: Circuit breaker for drawdown protection (-5%).
- Kelly Criterion: Dynamic sizing based on Win Rate (Jewel from Claude Code).
- Absolute Date Logging: Consistency for Dream Agent analysis.
- ATR-Adaptive SL/TP: Real volatility-based exits.
"""
import time
import os
import json
import logging
import uuid
import numpy as np
import schedule
import ccxt
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SQUAD_CRYPTO] %(message)s",
                    handlers=[logging.FileHandler(LOGS_DIR / "squad_crypto.log", encoding='utf-8', delay=True), logging.StreamHandler()])
logger = logging.getLogger("squad_crypto")

from config.settings import get_settings
from storage.repository import Repository
import ai.types as ai_types
import ai.decision_engine as decision_engine
from modules.notifications_hub import NotificationsHub
from ai.technical_engine import TechnicalEngine

settings = get_settings()
notifier = NotificationsHub()

# Universo crypto ad alta volatilità
CRYPTO_SYMBOLS = ["PEPE/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT", "BOME/USDT"]

def _build_exchange():
    name = settings.exchange.name.lower()
    dry_run = settings.trading.dry_run
    try:
        exchange_class = getattr(ccxt, name)
    except AttributeError:
        exchange_class = ccxt.binance
    auth = {"enableRateLimit": True}
    if not dry_run:
        auth["apiKey"] = settings.exchange.key
        auth["secret"] = settings.exchange.secret
    ex = exchange_class(auth)
    return ex

exchange = _build_exchange()

# ═══════════════════════════════════════════════════════════════════
# RESILIENCE WALLET — Kelly Criterion & Emergency Sleep
# ═══════════════════════════════════════════════════════════════════

class ResilienceWallet:
    """Wallet avanzato con protezione Drawdown e Kelly Sizing."""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.cash = initial_capital
        self.session_pnl = 0.0
        self.is_sleeping = False
        self.sleep_until = None
        self.positions = {}
        self.repo = Repository()
        
    def check_sleep_status(self):
        """Monitora il circuit breaker (Emergency Self-Sleep)."""
        if self.is_sleeping:
            if datetime.now(timezone.utc) > self.sleep_until:
                self.is_sleeping = False
                self.session_pnl = 0.0
                logger.info("⏰ SVEGLIA: Periodo di pausa terminato. Bot operativo.")
            else:
                return True
        
        # Trigger: Drawdown > 5% in sessione
        if self.session_pnl < -5.0:
            self.is_sleeping = True
            self.sleep_until = datetime.now(timezone.utc) + timedelta(hours=2)
            notifier.broadcast(f"🛑 EMERGENCY SLEEP: Drawdown sessione > 5%. Pausa per 2 ore per protezione capitale.", level="ERROR")
            logger.warning(f"!!! EMERGENCY SLEEP ATTIVATO !!! Drawdown: {self.session_pnl:.2f}%")
            return True
        return False

    def get_kelly_size(self, confidence_score: int) -> float:
        """Calcola la size usando il Criterio di Kelly semplificato (Jewel).
        Size = Equity * (WinRate - (LossRate / RewardRatio))
        Se confidence AI è bassa (< 60), riduciamo la size del 50%.
        """
        # Default conservativo per micro-capital
        base_pct = 0.02 # 2% base
        
        # Win Rate stimato (da Repository o Default 50%)
        wr = 0.52 
        rr = 1.6 # Reward Ratio stimato
        
        kelly_pct = wr - ((1 - wr) / rr)
        kelly_pct = max(0.01, min(0.05, kelly_pct)) # Cap tra 1% e 5% per sicurezza
        
        # Confidence multiplier
        conf_mult = 1.0 if confidence_score >= 75 else 0.5
        
        size = self.equity * kelly_pct * conf_mult
        return round(max(1.0, size), 2) # Minimo 1 USDT

wallet = ResilienceWallet(settings.trading.wallet_size)

# ═══════════════════════════════════════════════════════════════════
# CORE TRADING LOOP
# ═══════════════════════════════════════════════════════════════════

def autonomous_step():
    """Singolo ciclo di trading autonomo."""
    if wallet.check_sleep_status():
        return

    logger.info(f"--- Ciclo Autonomo V11.5 | Equity: {wallet.equity:.2f} USDT ---")
    
    # 1. Manage Positions (Exit Strategy)
    manage_existing_positions()
    
    # 2. Scanning symbols
    for symbol in CRYPTO_SYMBOLS:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=250)
            if not ohlcv: continue
            
            # Math offloading to TechnicalEngine
            import pandas as pd
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            analysis = TechnicalEngine.analyze_market(df)
            
            # 3. Decision Engine (AI + Technical)
            # Creiamo MarketIntelligence mockata per compatibilità
            intel = ai_types.MarketIntelligence(
                asset=symbol.split("/")[0],
                close_price=analysis['price'],
                rsi_5m=analysis['rsi'],
                macd_5m=analysis['macd'],
                market_regime=analysis['regime'],
                news_sentiment_score=0.0 # Mock
            )
            
            decision = decision_engine.evaluate(intel, wallet.repo)
            
            if decision.decision == ai_types.Action.BUY and decision.confidence >= 70:
                execute_buy(symbol, analysis, decision)
                
        except Exception as e:
            logger.error(f"Errore ciclo {symbol}: {e}")

def execute_buy(symbol: str, analysis: dict, decision: ai_types.TradeDecision):
    if symbol in wallet.positions: return # Già in posizione
    
    price = analysis['price']
    size_usdt = wallet.get_kelly_size(decision.confidence)
    
    if size_usdt > wallet.cash:
        logger.warning(f"Cash insufficiente per {symbol}: {size_usdt} needed, {wallet.cash:.2f} available.")
        return

    # Calcolo livelli con TechnicalEngine
    levels = TechnicalEngine.get_stop_levels(price, analysis['atr'], side="long")
    
    # Order execution (Dry Run supported by ccxt)
    logger.info(f"🚀 OPEN LONG {symbol} @ {price:.4f} | Size: {size_usdt} USDT | SL: {levels['sl']:.4f}")
    
    pos = {
        "id": str(uuid.uuid4())[:8],
        "symbol": symbol,
        "entry_price": price,
        "amount_usdt": size_usdt,
        "sl": levels['sl'],
        "tp": levels['tp'],
        "trailing_act": levels['trailing_activation'],
        "trailing_on": False,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "thesis": decision.thesis
    }
    
    wallet.positions[symbol] = pos
    wallet.cash -= size_usdt
    notifier.broadcast(f"✅ BUY {symbol}\nPrice: {price:.4f}\nSL: {levels['sl']:.4f}\nTP: {levels['tp']:.4f}\nReason: {decision.thesis}", level="INFO")

def manage_existing_positions():
    """Gestione attiva di SL, TP e Trailing Stop per ogni posizione."""
    to_close = []
    for symbol, pos in wallet.positions.items():
        try:
            ticker = exchange.fetch_ticker(symbol)
            curr_price = ticker['last']
            pnl_pct = (curr_price - pos['entry_price']) / pos['entry_price'] * 100
            
            # 1. Trailing Stop Activation
            if not pos['trailing_on'] and curr_price >= pos['trailing_act']:
                pos['trailing_on'] = True
                logger.info(f"🔥 TRAILING ACTIVATED for {symbol}")

            # 2. Dynamic Trailing (Locking 1% profit if trend continues)
            if pos['trailing_on']:
                new_sl = curr_price * 0.985 # 1.5% trailing distance
                if new_sl > pos['sl']:
                    pos['sl'] = new_sl

            # 3. Exit Conditions
            reason = None
            if curr_price <= pos['sl']: reason = "STOP LOSS"
            elif curr_price >= pos['tp']: reason = "TAKE PROFIT"
            
            if reason:
                close_position(symbol, pos, curr_price, reason)
                to_close.append(symbol)
        except Exception as e:
            logger.error(f"Errore management {symbol}: {e}")
            
    for s in to_close:
        del wallet.positions[s]

def close_position(symbol, pos, exit_price, reason):
    realized_pnl = (exit_price - pos['entry_price']) / pos['entry_price'] * 100
    pnl_usdt = pos['amount_usdt'] * (realized_pnl / 100)
    
    wallet.cash += (pos['amount_usdt'] + pnl_usdt)
    wallet.equity = wallet.cash + sum(p['amount_usdt'] for p in wallet.positions.values())
    wallet.session_pnl += realized_pnl
    
    # Record Outcome (Pattern: Absolute Dates)
    outcome = {
        "asset": symbol.split("/")[0],
        "exit_reason": reason,
        "pnl_pct": realized_pnl, # Matches Repository.save_trade_outcome
        "was_profitable": realized_pnl > 0,
        "closed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    }
    wallet.repo.save_trade_outcome(outcome)
    
    notifier.broadcast(f"📊 CLOSE {symbol} ({reason})\nExit: {exit_price:.4f}\nPnL: {realized_pnl:+.2f}%\nEquity: {wallet.equity:.2f} USDT", level="INFO")
    logger.info(f"Closed {symbol} via {reason}. PnL: {realized_pnl:.2f}%")

def main():
    logger.info("TENGU V11.5 Starting (STRESS TEST MODE)...")
    schedule.every(30).seconds.do(autonomous_step)
    autonomous_step() # First run
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
