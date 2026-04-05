"""
TENGU V11 — Squad Crypto: Autonomous Self-Evolving Trading Agent.

Ciclo perfetto: OBSERVE → ANALYZE → DECIDE → EXECUTE → MANAGE → RECORD → COMPOUND → DREAM → REPEAT

Features:
  - Dual Brain: AI (Gemma 4) + Technical Engine (RSI/MACD/BB)
  - Position Manager: SL, TP, Trailing Stop su ogni trade aperto
  - Compound Growth: profitti reinvestiti → position size cresce col capitale
  - Outcome Recording: ogni trade chiuso viene salvato in SuperBrain per il Dream Agent
  - Auto-Evolution: Dream Agent impara dai risultati e aggiorna le Golden Rules
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
tech_engine = TechnicalEngine(risk_pct=0.02, atr_sl_mult=1.5, atr_tp_mult=2.5)

# Universo crypto ad alta volatilità (memecoins per micro-capital)
CRYPTO_SYMBOLS = ["PEPE/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT", "BOME/USDT"]


# ═══════════════════════════════════════════════════════════════════
# CCXT Multi-Exchange Setup
# ═══════════════════════════════════════════════════════════════════

def _build_exchange():
    """Crea un'istanza CCXT basata su .env (EXCHANGE_NAME)."""
    name = settings.exchange.name.lower()
    dry_run = settings.trading.dry_run
    
    try:
        exchange_class = getattr(ccxt, name)
    except AttributeError:
        logger.warning(f"Exchange '{name}' non trovato in CCXT, fallback su 'binance'")
        exchange_class = ccxt.binance

    auth = {"enableRateLimit": True}
    
    if not dry_run:
        auth["apiKey"] = settings.exchange.key
        auth["secret"] = settings.exchange.secret
        if settings.exchange.password:
            auth["password"] = settings.exchange.password
    
    ex = exchange_class(auth)
    logger.info(f"📡 CCXT Exchange: {name.upper()} | DRY_RUN={dry_run}")
    return ex

exchange = _build_exchange()


# ═══════════════════════════════════════════════════════════════════
# Technical Analysis (Pure Math)
# ═══════════════════════════════════════════════════════════════════

def fetch_candles(symbol: str, timeframe: str = "5m", limit: int = 100) -> list:
    try:
        return exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    except Exception as e:
        logger.error(f"fetch_candles({symbol}, {timeframe}) fallito: {e}")
        return []

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
    return round(float(np.mean(trs[-period:])), 8)


# ═══════════════════════════════════════════════════════════════════
# COMPOUND WALLET — Il capitale cresce con i profitti
# ═══════════════════════════════════════════════════════════════════

class CompoundWallet:
    """Wallet con auto-compound. Da 50€ → guadagni 5€ → prossimo trade su 55€."""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.equity = initial_capital  # Equity totale (cash + posizioni)
        self.cash = initial_capital    # Cash disponibile
        self.total_pnl = 0.0          # PnL cumulativo
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.positions = {}            # {symbol: Position}
        self.trade_history = []        # Storico completo
        
    def get_position_size(self, risk_pct: float = 0.02) -> float:
        """Calcola la dimensione del trade basata sull'equity corrente.
        Compound: se hai 50€ e guadagni 10€, il prossimo trade è su 60€ × 2% = 1.2€
        """
        size = self.equity * risk_pct
        # Micro-capital guard: se troppo piccolo, usa il 5% dell'equity (min 1 USDT)
        if size < 1.0:
            size = max(1.0, self.equity * 0.05)
        # Safety cap: mai più del 10% in un singolo trade
        size = min(size, self.equity * 0.10)
        return round(size, 2)
    
    def open_position(self, symbol: str, price: float, usdt_amount: float, 
                      atr: float, source: str) -> dict:
        """Apri una posizione con SL/TP automatici basati su ATR."""
        if usdt_amount > self.cash:
            usdt_amount = self.cash * 0.95
        if usdt_amount < 0.50:
            return None
            
        qty = usdt_amount / price
        sl_price = price - (atr * 1.5)  # Stop Loss: 1.5 ATR sotto entry
        tp_price = price + (atr * 2.5)  # Take Profit: 2.5 ATR sopra entry
        
        position = {
            "symbol": symbol,
            "qty": qty,
            "entry_price": price,
            "usdt_in": usdt_amount,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "trailing_activated": False,
            "highest_price": price,
            "source": source,
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "order_id": f"SIM_{uuid.uuid4().hex[:8]}"
        }
        
        self.cash -= usdt_amount
        self.positions[symbol] = position
        
        sl_pct = ((sl_price - price) / price) * 100
        tp_pct = ((tp_price - price) / price) * 100
        logger.info(
            f"💰 [OPEN] {symbol} qty={qty:.6f} @ ${price:.8f} | "
            f"Spesa: ${usdt_amount:.2f} | SL: ${sl_price:.8f} ({sl_pct:+.1f}%) | "
            f"TP: ${tp_price:.8f} ({tp_pct:+.1f}%) | Source: {source}"
        )
        return position
    
    def close_position(self, symbol: str, exit_price: float, reason: str) -> dict:
        """Chiudi una posizione e registra l'esito."""
        if symbol not in self.positions:
            return None
        
        pos = self.positions.pop(symbol)
        usdt_out = pos["qty"] * exit_price
        pnl_usdt = usdt_out - pos["usdt_in"]
        pnl_pct = (pnl_usdt / pos["usdt_in"]) * 100
        
        # Compound: reinvesti il risultato nell'equity
        self.cash += usdt_out
        self.total_pnl += pnl_usdt
        self.equity = self.cash + sum(p["qty"] * p["entry_price"] for p in self.positions.values())
        self.total_trades += 1
        
        outcome = "WIN" if pnl_usdt > 0 else "LOSS" if pnl_usdt < -0.01 else "BREAKEVEN"
        if outcome == "WIN":
            self.wins += 1
        elif outcome == "LOSS":
            self.losses += 1
        
        duration_str = ""
        try:
            opened = datetime.fromisoformat(pos["opened_at"])
            duration = datetime.now(timezone.utc) - opened
            duration_str = str(duration).split(".")[0]
        except Exception:
            duration_str = "unknown"
        
        record = {
            "symbol": symbol,
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "qty": pos["qty"],
            "pnl_usdt": round(pnl_usdt, 4),
            "pnl_pct": round(pnl_pct, 2),
            "outcome": outcome,
            "reason": reason,
            "source": pos["source"],
            "duration": duration_str,
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "equity_after": round(self.equity, 2)
        }
        self.trade_history.append(record)
        
        emoji = "🟢" if outcome == "WIN" else "🔴" if outcome == "LOSS" else "⚪"
        logger.info(
            f"{emoji} [CLOSE] {symbol} | {outcome} {pnl_pct:+.2f}% (${pnl_usdt:+.4f}) | "
            f"Duration: {duration_str} | Reason: {reason} | "
            f"Equity: ${self.equity:.2f} (was ${self.initial_capital:.2f})"
        )
        return record
    
    def get_win_rate(self) -> float:
        if self.total_trades == 0: return 0.0
        return (self.wins / self.total_trades) * 100
    
    def get_growth_pct(self) -> float:
        if self.initial_capital == 0: return 0.0
        return ((self.equity - self.initial_capital) / self.initial_capital) * 100


# ═══════════════════════════════════════════════════════════════════
# POSITION MANAGER — Monitora SL/TP/Trailing ogni ciclo
# ═══════════════════════════════════════════════════════════════════

def manage_positions(wallet: CompoundWallet, repo: Repository):
    """Controlla ogni posizione aperta per SL, TP, e Trailing Stop.
    Pattern: Run Tests WITH the feature enabled (coordinatorMode.ts)
    Non rubber-stampa — verifica realmente il prezzo corrente."""
    
    # Copia le chiavi per evitare "dictionary changed size" durante iterazione
    symbols_to_check = list(wallet.positions.keys())
    
    for symbol in symbols_to_check:
        if symbol not in wallet.positions:
            continue
        pos = wallet.positions[symbol]
        
        try:
            # Fetch prezzo attuale
            candles = fetch_candles(symbol, "5m", 5)
            if not candles:
                continue
            current_price = float(candles[-1][4])
            
            # Aggiorna highest price per trailing
            if current_price > pos["highest_price"]:
                pos["highest_price"] = current_price
            
            pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100
            
            # ── STOP LOSS ──
            if current_price <= pos["sl_price"]:
                record = wallet.close_position(symbol, current_price, f"STOP_LOSS (price ${current_price:.8f} <= SL ${pos['sl_price']:.8f})")
                if record:
                    _record_outcome(record, repo)
                    notifier.broadcast(f"🔴 STOP LOSS {symbol}\nPnL: {record['pnl_pct']:+.2f}%\nEquity: ${record['equity_after']:.2f}")
                continue
            
            # ── TAKE PROFIT ──
            if current_price >= pos["tp_price"]:
                record = wallet.close_position(symbol, current_price, f"TAKE_PROFIT (price ${current_price:.8f} >= TP ${pos['tp_price']:.8f})")
                if record:
                    _record_outcome(record, repo)
                    notifier.broadcast(f"🟢 TAKE PROFIT {symbol}\nPnL: {record['pnl_pct']:+.2f}%\nEquity: ${record['equity_after']:.2f}")
                continue
            
            # ── TRAILING STOP ──
            # Se in profitto > 1.5%, attiva trailing: SL = highest_price - (ATR × 1.0)
            if pnl_pct > 1.5 and not pos.get("trailing_activated"):
                # Ricalcola ATR con dati freschi
                candles_100 = fetch_candles(symbol, "5m", 50)
                if candles_100 and len(candles_100) > 15:
                    h = [float(x[2]) for x in candles_100]
                    l = [float(x[3]) for x in candles_100]
                    c = [float(x[4]) for x in candles_100]
                    atr = compute_atr(h, l, c)
                    if atr > 0:
                        # Trailing: alza SL al breakeven + margine
                        new_sl = pos["entry_price"] * 1.003  # SL al breakeven + 0.3%
                        if new_sl > pos["sl_price"]:
                            pos["sl_price"] = new_sl
                            pos["trailing_activated"] = True
                            logger.info(f"📈 [TRAILING] {symbol} SL alzato a breakeven+0.3% = ${new_sl:.8f} (PnL: {pnl_pct:+.1f}%)")
            
            # Se trailing attivo e profitto > 3%, stringa ulteriormente lo SL
            if pos.get("trailing_activated") and pnl_pct > 3.0:
                new_sl = pos["highest_price"] * 0.985  # SL al -1.5% dal massimo
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    logger.info(f"📈 [TRAILING++] {symbol} SL stretto a ${new_sl:.8f} (high: ${pos['highest_price']:.8f}, PnL: {pnl_pct:+.1f}%)")
            
            # ── TIME-BASED EXIT ──
            # Se la posizione è aperta da > 4 ore e PnL è negativo, chiudi
            try:
                opened = datetime.fromisoformat(pos["opened_at"])
                age_hours = (datetime.now(timezone.utc) - opened).total_seconds() / 3600
                if age_hours > 4 and pnl_pct < -0.5:
                    record = wallet.close_position(symbol, current_price, f"TIME_EXIT (>{age_hours:.0f}h, PnL {pnl_pct:+.1f}%)")
                    if record:
                        _record_outcome(record, repo)
                    continue
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Position manager error for {symbol}: {e}")


def _record_outcome(record: dict, repo: Repository):
    """Registra l'esito del trade in SuperBrain per il Dream Agent.
    Pattern: Structured Feedback (Rule/Why/How to apply) da memoryTypes.ts.
    """
    try:
        # 1. Salva nel repository (SQLite)
        repo.save_trade_outcome({
            "asset": record["symbol"],
            "entry_price": record["entry_price"],
            "exit_price": record["exit_price"],
            "pnl_pct": record["pnl_pct"],
            "was_profitable": record["outcome"] == "WIN",
            "realized_pnl_pct": record["pnl_pct"],
            "reason": record["reason"],
            "source": record["source"],
            "duration": record["duration"]
        })
    except Exception as e:
        logger.debug(f"save_trade_outcome non supportato: {e}")
    
    try:
        # 2. Salva in SuperBrain con feedback strutturato (Rule/Why/How)
        from storage.superbrain import get_superbrain
        brain = get_superbrain()
        
        feedback = (
            f"Trade Result: {record['outcome']} on {record['symbol']}\n"
            f"Rule: {record['source']} strategy → {record['outcome']} ({record['pnl_pct']:+.2f}%)\n"
            f"Why: Entry at ${record['entry_price']:.8f}, exit at ${record['exit_price']:.8f}, "
            f"closed by {record['reason']} after {record['duration']}\n"
            f"How to apply: {'Increase confidence for' if record['outcome'] == 'WIN' else 'Review conditions for'} "
            f"{record['source']} on {record['symbol']}\n"
            f"Equity after: ${record['equity_after']:.2f}"
        )
        
        brain.remember_feedback(feedback, agent="squad_crypto_v11")
        brain.remember_market_signal(
            record["symbol"],
            f"{record['outcome']}: {record['pnl_pct']:+.2f}% via {record['source']} ({record['reason']})",
            confidence=80 if record["outcome"] == "WIN" else 30
        )
    except Exception as e:
        logger.debug(f"SuperBrain recording failed (non-critical): {e}")
    
    try:
        # 3. Log nell'activity log
        repo.log_activity(
            "squad_crypto", record["outcome"],
            f"{record['symbol']} {record['pnl_pct']:+.2f}% via {record['source']} | Equity: ${record['equity_after']:.2f}"
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# MAIN TRADING CYCLE — Il ciclo perfetto
# ═══════════════════════════════════════════════════════════════════

# Compound Wallet singleton (sopravvive tra i cicli)
wallet = CompoundWallet(initial_capital=settings.trading.wallet_size)

def job_crypto_cycle(repo: Repository):
    """Ciclo completo autonomo:
    1. OBSERVE  → Fetch OHLCV + stato sistema
    2. ANALYZE  → AI + Technical Engine
    3. DECIDE   → Dual Brain consensus
    4. EXECUTE  → Buy se segnale valido
    5. MANAGE   → Monitora posizioni aperte (SL/TP/Trailing)
    6. RECORD   → Salva esiti in SuperBrain
    7. COMPOUND → La prossima position size riflette l'equity aggiornata
    """
    cycle_start = time.time()
    dry_run = settings.trading.dry_run
    
    try:
        # ── PRE-CHECK: Emergency Stop ──
        controls = repo.get_supervisor_controls()
        if controls.get("emergency_stop", 0):
            logger.warning("⛔ EMERGENCY_STOP ACTIVE. Ciclo saltato.")
            return

        max_trades = controls.get("max_open_trades", settings.risk.max_open_trades)
        min_conf = controls.get("min_confidence", settings.risk.min_confidence_buy)
        if dry_run:
            min_conf = min(min_conf, 45)

        # ── STEP 5: MANAGE — Controlla posizioni PRIMA di cercare nuovi segnali ──
        if wallet.positions:
            manage_positions(wallet, repo)

        # ── STEP 1-4: OBSERVE → ANALYZE → DECIDE → EXECUTE ──
        open_symbols = set(wallet.positions.keys())
        open_trades_db = repo.get_open_decisions()
        analyzed = 0
        signals = 0

        for sym in CRYPTO_SYMBOLS:
            try:
                # Skip se posizione già aperta
                if sym in open_symbols or any(t.get("asset") == sym for t in open_trades_db):
                    continue
                
                # Skip se troppi trade aperti
                if len(wallet.positions) >= max_trades:
                    break

                # 1. OBSERVE
                k5 = fetch_candles(sym, "5m", 100)
                k1h = fetch_candles(sym, "1h", 100)
                
                if not k5 or len(k5) < 30:
                    continue
                
                c5 = [float(x[4]) for x in k5]
                h5 = [float(x[2]) for x in k5]
                l5 = [float(x[3]) for x in k5]
                c1h = [float(x[4]) for x in k1h] if k1h and len(k1h) > 5 else c5
                
                price = c5[-1]
                rsi5 = compute_rsi(c5)
                rsi1h = compute_rsi(c1h)
                macd5 = compute_macd(c5)
                macd1h = compute_macd(c1h)
                atr5 = compute_atr(h5, l5, c5)
                
                # 2. ANALYZE — Dual Brain
                # 2A: Technical Engine (veloce)
                tech_signal = tech_engine.evaluate(np.array(c5), np.array(h5), np.array(l5))
                
                # 2B: AI LLM (profondo)
                ai_action, ai_conf, ai_thesis, ai_monologue = "hold", 0, "LLM skipped", ""
                try:
                    intel = ai_types.MarketIntelligence(
                        asset=sym, close_price=price, rsi_5m=rsi5, rsi_1h=rsi1h,
                        macd_5m=macd5, macd_1h=macd1h, market_regime="UNKNOWN",
                        news_count=3, research_staleness_seconds=10.0
                    )
                    ai_decision = decision_engine.evaluate(intel, repo)
                    ai_action = ai_decision.decision.value
                    ai_conf = ai_decision.confidence
                    ai_thesis = ai_decision.thesis
                    ai_monologue = ai_decision.inner_monologue
                except Exception as ai_err:
                    logger.warning(f"🧠 AI non disponibile per {sym}: {ai_err}")
                
                analyzed += 1
                
                # 3. DECIDE — Chi comanda?
                final_action = "hold"
                final_conf = 0
                final_reason = ""
                decision_source = "NONE"
                
                if ai_action == "buy" and ai_conf >= min_conf:
                    final_action = "buy"
                    final_conf = ai_conf
                    final_reason = f"[AI] {ai_thesis}"
                    decision_source = "AI_LLM"
                elif tech_signal.action == "BUY" and tech_signal.confidence >= 60:
                    final_action = "buy"
                    final_conf = tech_signal.confidence
                    final_reason = f"[TECH] {tech_signal.reason}"
                    decision_source = tech_signal.strategy
                else:
                    final_reason = f"[AI:{ai_action}@{ai_conf}%] [TECH:{tech_signal.action}@{tech_signal.confidence}%]"
                
                regime = "TREND_UP" if macd5 > 0 and rsi5 > 50 else "TREND_DOWN" if macd5 < 0 and rsi5 < 40 else "RANGING"
                
                # Salva snapshot nel DB per la dashboard
                repo.upsert_market_snapshot({
                    "asset": sym, "price": price, "rsi_5m": rsi5, "rsi_1h": rsi1h,
                    "macd_5m": macd5, "macd_1h": macd1h, "atr_5m": atr5,
                    "decision": final_action, "confidence": final_conf,
                    "regime": regime, "consensus_score": final_conf / 100.0,
                    "position_size_pct": 0.0, "atr_stop_distance": atr5 * 1.5,
                    "why_not_trade": final_reason
                })
                
                logger.info(f"📊 {sym} ${price:.8f} | RSI={rsi5:.0f} MACD={macd5:.6f} | {final_action.upper()} via {decision_source} @{final_conf}%")
                
                # 4. EXECUTE — Solo se tutti i filtri passano
                if final_action == "buy" and final_conf >= min_conf and regime != "TREND_DOWN":
                    signals += 1
                    
                    # Compound position sizing
                    pos_value = wallet.get_position_size(risk_pct=0.02)
                    
                    position = wallet.open_position(
                        symbol=sym, price=price, usdt_amount=pos_value,
                        atr=atr5, source=decision_source
                    )
                    
                    if position:
                        repo.save_trade_decision({
                            "id": f"DEC-CRYPTO-{uuid.uuid4().hex[:8]}", 
                            "asset": sym, "action": "buy",
                            "confidence": final_conf, 
                            "size_pct": pos_value / wallet.equity if wallet.equity > 0 else 0.02,
                            "thesis": final_reason, "regime": regime,
                            "entry_price": price, "atr_stop_distance": atr5 * 1.5,
                            "status": "OPEN", "inner_monologue": ai_monologue,
                            "agent_name": f"Squad-Crypto-V11/{decision_source}", 
                            "exchange_order_id": position["order_id"]
                        })
                        repo.log_activity("squad_crypto", "BUY", 
                            f"{sym} @ ${price:.8f} | {decision_source} Conf:{final_conf}% | Size: ${pos_value:.2f}")
                        notifier.broadcast(
                            f"🟢 BUY {sym} @ ${price:.8f}\n"
                            f"Source: {decision_source} | Conf: {final_conf}%\n"
                            f"Size: ${pos_value:.2f} | SL: ${position['sl_price']:.8f} | TP: ${position['tp_price']:.8f}\n"
                            f"Equity: ${wallet.equity:.2f} (+{wallet.get_growth_pct():.1f}%)"
                        )
                    
            except Exception as e:
                logger.error(f"Errore su {sym}: {e}")

        # ── Heartbeat con stato completo ──
        elapsed = round(time.time() - cycle_start, 1)
        heartbeat = {
            "mode": "DRY_RUN" if dry_run else "LIVE",
            "exchange": settings.exchange.name.upper(),
            "last_run": datetime.now(timezone.utc).isoformat(),
            "analyzed": analyzed, "signals": signals, "elapsed_s": elapsed,
            "equity": round(wallet.equity, 2),
            "cash": round(wallet.cash, 2),
            "initial_capital": wallet.initial_capital,
            "growth_pct": round(wallet.get_growth_pct(), 2),
            "total_pnl": round(wallet.total_pnl, 4),
            "open_positions": len(wallet.positions),
            "total_trades": wallet.total_trades,
            "win_rate": round(wallet.get_win_rate(), 1),
            "wins": wallet.wins, "losses": wallet.losses
        }
        repo.update_service_heartbeat("squad_crypto", json.dumps(heartbeat))
        repo.log_activity("squad_crypto", "CYCLE", 
            f"{analyzed}/{len(CRYPTO_SYMBOLS)} analizzati in {elapsed}s | "
            f"Signals: {signals} | Positions: {len(wallet.positions)} | "
            f"Equity: ${wallet.equity:.2f} ({wallet.get_growth_pct():+.1f}%) | "
            f"WR: {wallet.get_win_rate():.0f}% ({wallet.wins}W/{wallet.losses}L)")
        
        logger.info(
            f"✅ Ciclo #{wallet.total_trades + len(wallet.positions)} completato in {elapsed}s — "
            f"Equity: ${wallet.equity:.2f} ({wallet.get_growth_pct():+.1f}%) | "
            f"Open: {len(wallet.positions)} | WR: {wallet.get_win_rate():.0f}%"
        )
        
    except Exception as e:
        logger.error(f"ERRORE CRITICO: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════
# MAIN — Avvio autonomo
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info(
        f"🚀 Squad Crypto V11 (Autonomous Compound) avviato!\n"
        f"   Exchange: {settings.exchange.name.upper()} | DRY_RUN={settings.trading.dry_run}\n"
        f"   Capitale iniziale: ${wallet.initial_capital:.2f}\n"
        f"   Symbols: {', '.join(CRYPTO_SYMBOLS)}\n"
        f"   Risk per trade: 2% equity | Max open: {settings.risk.max_open_trades}\n"
        f"   SL: 1.5×ATR | TP: 2.5×ATR | Trailing: >1.5% profit"
    )
    repo = Repository()
    
    # Ciclo ogni 60 secondi 
    schedule.every(60).seconds.do(job_crypto_cycle, repo)
    job_crypto_cycle(repo)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
