"""
TENGU V12 — SQUAD CRYPTO (UPGRADED)
========================================
Upgrade V12:
  [V12-1] Token Scoring Engine — valuta ogni coin 0-100 prima dell'AI.
  [V12-2] Gem Scanner — scopre automaticamente nuove gemme dall'exchange.
  [V12-3] Multi-Timeframe Analysis — conferma segnali 5m con trend 1h.
  [V12-4] Dynamic ATR Stop-Loss — SL/TP adattivi alla volatilità.
Fix preservati: FIX-1 through FIX-5.
"""
import sys
import time
import os
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import schedule
import ccxt
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SQUAD_CRYPTO] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "squad_crypto.log", encoding="utf-8", delay=True),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("squad_crypto")

from config.settings import get_settings
from storage.repository import Repository
import ai.types as ai_types
import ai.decision_engine as decision_engine
from modules.notifications_hub import NotificationsHub
from ai.technical_engine import TechnicalEngine
from ai.token_scorer import TokenScorer
from ai.gem_scanner import GemScanner
from storage.superbrain import get_superbrain

settings = get_settings()
brain = get_superbrain()
notifier = NotificationsHub()

# Lista base (le gem scoperte si aggiungono dinamicamente)
BASE_CRYPTO_SYMBOLS = ["PEPE/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT", "BOME/USDT"]

# Simboli attivi (base + gem scoperte)
active_symbols: list[str] = list(BASE_CRYPTO_SYMBOLS)

# Istanze globali V12
token_scorer = TokenScorer()
GEM_SCAN_INTERVAL_CYCLES = 30  # Ogni 30 cicli (~15 min) scansiona nuove gem
_cycle_counter = 0

# ──────────────────────────────────────────────────────────────────
# EXCHANGE FACTORY
# ──────────────────────────────────────────────────────────────────

def _build_exchange() -> ccxt.Exchange:
    name = settings.exchange.name.lower()
    try:
        exchange_class = getattr(ccxt, name)
    except AttributeError:
        logger.warning(f"Exchange '{name}' non trovato in ccxt — fallback su Binance.")
        exchange_class = ccxt.binance

    auth = {"enableRateLimit": True}
    if not settings.trading.dry_run:
        auth["apiKey"] = settings.exchange.key
        auth["secret"] = settings.exchange.secret

    return exchange_class(auth)


exchange = _build_exchange()

# ──────────────────────────────────────────────────────────────────
# RESILIENCE WALLET — Kelly Criterion & Emergency Sleep
# [FIX-1] equity calcolata su mark-to-market, non su amount_usdt statico
# [FIX-3] Kelly usa win rate reale dal Repository
# ──────────────────────────────────────────────────────────────────

class ResilienceWallet:
    """Wallet con protezione Drawdown, Kelly sizing e Emergency Sleep."""

    DRAWDOWN_THRESHOLD_PCT = -5.0
    SLEEP_HOURS = 2
    KELLY_MIN_PCT = 0.01
    KELLY_MAX_PCT = 0.05
    MIN_SIZE_USDT = 15.0

    def __init__(self, initial_capital: float, repo: Repository):
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.cash = initial_capital
        self.session_pnl: float = 0.0
        self.is_sleeping: bool = False
        self.sleep_until: datetime | None = None
        self.positions: dict = {}  # symbol -> position dict
        self.repo = repo
        from pathlib import Path
        import json
        self.state_file = Path("user_cache/wallet_state.json")
        self.load_state()

    def load_state(self) -> None:
        if self.state_file.exists():
            try:
                import json
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                self.equity = state.get("equity", self.initial_capital)
                self.cash = state.get("cash", self.initial_capital)
                self.positions = state.get("positions", {})
                self.session_pnl = state.get("session_pnl", 0.0)
            except Exception as e:
                logger.error(f"Errore load wallet state: {e}")

    def save_state(self) -> None:
        try:
            import json
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump({
                    "equity": self.equity,
                    "cash": self.cash,
                    "positions": self.positions,
                    "session_pnl": self.session_pnl
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Errore save wallet state: {e}")

    # ── Sleep Logic ──────────────────────────────────────────────

    def check_sleep_status(self) -> bool:
        """Ritorna True se il bot e' in pausa (non deve operare)."""
        if self.is_sleeping:
            if datetime.now(timezone.utc) > self.sleep_until:
                self.is_sleeping = False
                self.session_pnl = 0.0
                logger.info("SVEGLIA: Periodo di pausa terminato. Bot operativo.")
            else:
                remaining = (self.sleep_until - datetime.now(timezone.utc)).seconds // 60
                logger.info(f"SLEEPING — {remaining} min rimanenti.")
                return True

        if self.session_pnl < self.DRAWDOWN_THRESHOLD_PCT:
            self.is_sleeping = True
            self.sleep_until = datetime.now(timezone.utc) + timedelta(hours=self.SLEEP_HOURS)
            msg = (
                f"EMERGENCY SLEEP: Drawdown sessione {self.session_pnl:.2f}% "
                f"(soglia {self.DRAWDOWN_THRESHOLD_PCT}%). Pausa per {self.SLEEP_HOURS} ore."
            )
            notifier.broadcast(msg, level="ERROR")
            logger.warning(msg)
            return True

        return False

    # ── Kelly Criterion ──────────────────────────────────────────
    # [FIX-3] Win Rate letto dal Repository (ultimi 30 trade)

    def get_kelly_size(self, confidence_score: int) -> float:
        """
        Calcola la size usando il Kelly Criterion.
        Win Rate e Reward Ratio derivati dai trade storici reali.
        Se dati insufficienti (<5 trade) usa default conservativo 2%.
        """
        try:
            outcomes = self.repo.get_recent_outcomes(days=30)
            if len(outcomes) >= 5:
                wins = sum(1 for o in outcomes if o.get("was_profitable", False))
                wr = wins / len(outcomes)
                win_pnls = [abs(o["pnl_pct"]) for o in outcomes if o.get("was_profitable") and o.get("pnl_pct")]
                loss_pnls = [abs(o["pnl_pct"]) for o in outcomes if not o.get("was_profitable") and o.get("pnl_pct")]
                rr = (sum(win_pnls) / len(win_pnls)) / (sum(loss_pnls) / len(loss_pnls)) if win_pnls and loss_pnls else 1.5
                kelly_pct = wr - ((1 - wr) / rr)
                logger.debug(f"Kelly real: WR={wr:.2%}, RR={rr:.2f}, K={kelly_pct:.4f} ({len(outcomes)} trade)")
            else:
                logger.debug(f"Kelly default (solo {len(outcomes)} trade disponibili).")
                kelly_pct = 0.02
        except Exception as e:
            logger.warning(f"Kelly fallback (errore lettura repo): {e}")
            kelly_pct = 0.02

        kelly_pct = max(self.KELLY_MIN_PCT, min(self.KELLY_MAX_PCT, kelly_pct))
        conf_multiplier = 1.0 if confidence_score >= 75 else 0.5
        size = self.equity * kelly_pct * conf_multiplier
        return round(max(self.MIN_SIZE_USDT, size), 2)

    # ── Mark-to-Market Equity ────────────────────────────────────
    # [FIX-1] Usa il prezzo di mercato corrente, non amount_usdt statico

    def recalculate_equity(self) -> None:
        """
        Aggiorna self.equity = cash + valore corrente di tutte le posizioni aperte.
        Chiamata dopo ogni chiusura e opzionalmente ogni ciclo.
        """
        open_value = 0.0
        for symbol, pos in self.positions.items():
            try:
                ticker = exchange.fetch_ticker(symbol)
                curr_price = ticker["last"]
                qty = pos["amount_usdt"] / pos["entry_price"]
                open_value += qty * curr_price
            except Exception:
                open_value += pos["amount_usdt"]
        self.equity = round(self.cash + open_value, 4)
        self.save_state()


# ──────────────────────────────────────────────────────────────────
# TRADING CORE
# ──────────────────────────────────────────────────────────────────

repo = Repository()
wallet = ResilienceWallet(settings.trading.wallet_size, repo)


def autonomous_step() -> None:
    """Singolo ciclo di trading autonomo V12."""
    global _cycle_counter, active_symbols
    
    if wallet.check_sleep_status():
        return

    _cycle_counter += 1

    logger.info(
        f"Ciclo V12 #{_cycle_counter} | Equity: {wallet.equity:.2f} USDT | "
        f"Cash: {wallet.cash:.2f} | Posizioni: {len(wallet.positions)} | "
        f"Symbols attivi: {len(active_symbols)}"
    )

    # [V12-2] GEM SCANNER — scopri nuove gemme periodicamente
    if _cycle_counter % GEM_SCAN_INTERVAL_CYCLES == 1:
        try:
            scanner = GemScanner(exchange, existing_symbols=active_symbols)
            gems = scanner.scan(strategy="all")
            for gem in gems:
                if gem.symbol not in active_symbols:
                    active_symbols.append(gem.symbol)
                    logger.info(f"[GEM] Nuova gem aggiunta: {gem.symbol} ({gem.discovery_reason}, +{gem.change_24h:.1f}%)")
                    notifier.broadcast(
                        f"💎 NUOVA GEM: {gem.symbol}\n"
                        f"Change 24h: {gem.change_24h:+.1f}%\n"
                        f"Volume: ${gem.volume_24h_usd/1e6:.2f}M\n"
                        f"Motivo: {gem.discovery_reason}",
                        level="INFO",
                    )
                    # [V12-SUPERMEMORY] Salva la scoperta nella memoria collettiva
                    brain.remember_gem(gem.symbol, gem.discovery_reason, gem.change_24h, gem.volume_24h_usd)
                    repo.log_activity("squad_crypto", "GEM_DISCOVERY", f"Nuova gemma rilevata: {gem.symbol} ({gem.discovery_reason})")
            # Mantieni max 15 simboli attivi (base + gem)
            if len(active_symbols) > 15:
                active_symbols = list(BASE_CRYPTO_SYMBOLS) + active_symbols[len(BASE_CRYPTO_SYMBOLS):][:10]
        except Exception as e:
            logger.error(f"[GEM_SCANNER] Errore: {e}")

    repo.update_service_heartbeat("squad_crypto", json.dumps({
        "status": "running",
        "equity": wallet.equity,
        "open_positions": list(wallet.positions.keys()),
        "session_pnl": wallet.session_pnl,
        "active_symbols": active_symbols,
        "cycle": _cycle_counter,
    }))

    _manage_existing_positions()

    controls = repo.get_supervisor_controls()
    if controls.get("emergency_stop", 0):
        logger.warning("Emergency Stop attivo (Risk Controller). Nessun nuovo trade.")
        return

    max_open = controls.get("max_open_trades", 2)
    min_conf = controls.get("min_confidence", 70)

    for symbol in active_symbols:
        if len(wallet.positions) >= max_open:
            logger.info(f"Max posizioni aperte ({max_open}) raggiunto. Skip scan.")
            break
        
        # [V12-ACTIVITY] Segnala cosa sta facendo il bot sulla dashboard (Orologio Puntuale)
        repo.log_activity("squad_crypto", "SCANNING", f"Analisi tecnica e scoring per {symbol}")
        _scan_symbol(symbol, min_conf)


def _scan_symbol(symbol: str, min_confidence: int) -> None:
    try:
        # Fetch 5m OHLCV
        ohlcv_5m = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=250)
        if not ohlcv_5m or len(ohlcv_5m) < 50:
            logger.warning(f"Dati OHLCV 5m insufficienti per {symbol}.")
            return

        df_5m = pd.DataFrame(ohlcv_5m, columns=["timestamp", "open", "high", "low", "close", "volume"])

        # [V12-1] TOKEN SCORING — valuta prima di chiamare l'AI
        try:
            ticker = exchange.fetch_ticker(symbol)
        except Exception:
            ticker = None

        score = token_scorer.score(symbol, df_5m, ticker)
        
        if not score.is_tradeable:
            logger.info(f"SKIP {symbol} | Score: {score.total}/100 ({score.action}) — sotto soglia 70")
            return

        # [V12-3] MULTI-TIMEFRAME — fetch 1h e analizza
        try:
            ohlcv_1h = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=250)
            df_1h = pd.DataFrame(ohlcv_1h, columns=["timestamp", "open", "high", "low", "close", "volume"])
        except Exception:
            df_1h = None

        mtf_result = TechnicalEngine.analyze_multi_timeframe(df_5m, df_1h)
        analysis = mtf_result.get("analysis_5m", {})
        
        if not analysis:
            logger.warning(f"Analisi tecnica fallita per {symbol}")
            return

        # Costruisci MarketIntelligence arricchita
        intel = ai_types.MarketIntelligence(
            asset=symbol.split("/")[0],
            close_price=analysis["price"],
            rsi_5m=analysis["rsi"],
            macd_5m=analysis["macd"],
            rsi_1h=mtf_result.get("htf_rsi", 50.0),
            market_regime=analysis["regime"],
            news_sentiment_score=0.0,
        )

        # [V12-CLOCKWORK] Segnala i dettagli tecnici REALI *prima* della decisione lenta del Brain
        repo.log_activity("squad_crypto", "SCANNING", 
            f"⚡ ANALISI {symbol} | Prezzo: {analysis['price']:.6f} | RSI: {analysis['rsi']:.1f} | Score: {score.total}/100"
        )
        
        # [V12-SYNC] Avviso che il Cervello sta decidendo
        repo.log_activity("squad_crypto", "THINKING", f"🧠 Gemma 4 sta elaborando la tesi per {symbol}...")

        decision = decision_engine.evaluate(intel, repo)

        logger.info(
            f"SCAN {symbol} | Score: {score.total}/100 ({score.action}) | "
            f"Price: {analysis['price']:.6f} | RSI: {analysis['rsi']:.1f} | "
            f"Regime: {analysis['regime']} | HTF: {mtf_result['htf_regime']} | "
            f"Decision: {decision.decision.value} ({decision.confidence}%)"
        )

        if decision.decision == ai_types.Action.BUY and decision.confidence >= min_confidence:
            # Salva score nel contesto per audit
            analysis["token_score"] = score.total
            analysis["token_action"] = score.action
            analysis["htf_regime"] = mtf_result.get("htf_regime", "UNKNOWN")
            analysis["htf_aligned"] = mtf_result.get("htf_alignment", False)
            _execute_buy(symbol, analysis, decision)

    except Exception as e:
        logger.error(f"Errore scan {symbol}: {e}", exc_info=True)


def _execute_buy(symbol: str, analysis: dict, decision: ai_types.TradeDecision) -> None:
    if symbol in wallet.positions:
        logger.info(f"Gia' in posizione su {symbol} — skip.")
        return

    price = analysis["price"]
    size_usdt = wallet.get_kelly_size(decision.confidence)

    if size_usdt > wallet.cash:
        logger.warning(f"Cash insufficiente per {symbol}: richiesti {size_usdt:.2f}, disponibili {wallet.cash:.2f}")
        return

    levels = TechnicalEngine.get_stop_levels(price, analysis["atr"], side="long")

    logger.info(
        f"OPEN LONG {symbol} @ {price:.6f} | Size: {size_usdt} USDT | "
        f"SL: {levels['sl']:.6f} | TP: {levels['tp']:.6f}"
    )

    decision_uuid = str(uuid.uuid4())[:8]
    pos = {
        "id": decision_uuid,
        "symbol": symbol,
        "entry_price": price,
        "amount_usdt": size_usdt,
        "sl": levels["sl"],
        "tp": levels["tp"],
        "trailing_activation": levels["trailing_activation"],
        "trailing_on": False,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "thesis": decision.thesis,
    }

    wallet.positions[symbol] = pos
    wallet.cash -= size_usdt
    wallet.recalculate_equity()
    
    # [V12-4] Fix Dashboard Visibility: save decision to repo
    try:
        repo.save_trade_decision({
            "id": decision_uuid,
            "asset": symbol.split("/")[0],
            "action": decision.decision.value,
            "confidence": decision.confidence,
            "size_pct": size_usdt, # approx using absolute size for now
            "thesis": decision.thesis,
            "regime": analysis.get("regime", "UNKNOWN"),
            "entry_price": price,
            "atr_stop_distance": float(analysis.get("atr", 0.0)),
            "status": "OPEN",
            "agent_name": "squad_crypto",
        })
    except Exception as e:
        logger.error(f"Errore save_trade_decision: {e}")

    notifier.broadcast(
        f"BUY {symbol}\nPrice: {price:.6f}\nSL: {levels['sl']:.6f} | TP: {levels['tp']:.6f}\n"
        f"Size: {size_usdt} USDT\nThesis: {decision.thesis}",
        level="INFO",
    )


def _manage_existing_positions() -> None:
    """Gestione SL, TP e Trailing Stop per ogni posizione aperta."""
    to_close = []

    for symbol, pos in list(wallet.positions.items()):
        try:
            ticker = exchange.fetch_ticker(symbol)
            curr_price = ticker["last"]

            if not pos["trailing_on"] and curr_price >= pos["trailing_activation"]:
                pos["trailing_on"] = True
                logger.info(f"TRAILING ACTIVATED: {symbol} @ {curr_price:.6f}")

            if pos["trailing_on"]:
                candidate_sl = curr_price * 0.985
                if candidate_sl > pos["sl"]:
                    pos["sl"] = candidate_sl

            reason = None
            if curr_price <= pos["sl"]:
                reason = "STOP_LOSS"
            elif curr_price >= pos["tp"]:
                reason = "TAKE_PROFIT"

            if reason:
                _close_position(symbol, pos, curr_price, reason)
                to_close.append(symbol)
            else:
                pnl_pct = (curr_price - pos["entry_price"]) / pos["entry_price"] * 100
                logger.info(f"  {symbol}: curr={curr_price:.6f} | PnL={pnl_pct:+.2f}% | SL={pos['sl']:.6f}")

        except Exception as e:
            logger.error(f"Errore management {symbol}: {e}")

    for s in to_close:
        del wallet.positions[s]

    if to_close:
        wallet.recalculate_equity()  # [FIX-1] ricalcolo dopo rimozioni


def _close_position(symbol: str, pos: dict, exit_price: float, reason: str) -> None:
    """Chiude una posizione e registra l'outcome. Campo pnl_pct unificato. [FIX-2]"""
    pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
    pnl_usdt = pos["amount_usdt"] * (pnl_pct / 100)

    wallet.cash += pos["amount_usdt"] + pnl_usdt
    wallet.session_pnl += pnl_pct

    # [FIX-2] Campo standardizzato: "pnl_pct"
    outcome = {
        "decision_id": pos["id"],  # Connects outcome to the decision ID for SQL INNER JOIN
        "asset": symbol.split("/")[0],
        "symbol": symbol,
        "entry_price": pos["entry_price"],
        "exit_price": exit_price,
        "exit_reason": reason,
        "pnl_pct": round(pnl_pct, 4),
        "pnl_usdt": round(pnl_usdt, 4),
        "was_profitable": pnl_pct > 0,
        "thesis": pos.get("thesis", ""),
        "opened_at": pos["opened_at"],
        "closed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    repo.save_trade_outcome(outcome)
    
    # Close decision in repo to remove from active display
    try:
        repo.update_decision_status(pos["id"], "CLOSED")
    except Exception:
        pass

    status = "WIN" if pnl_pct > 0 else "LOSS"
    notifier.broadcast(
        f"CLOSE {symbol} ({reason}) [{status}]\n"
        f"Exit: {exit_price:.6f} | PnL: {pnl_pct:+.2f}% ({pnl_usdt:+.4f} USDT)\n"
        f"Equity: {wallet.equity:.2f} USDT",
        level="INFO",
    )
    logger.info(f"Closed {symbol} via {reason}. PnL: {pnl_pct:.4f}% ({pnl_usdt:.4f} USDT)")


def main() -> None:
    logger.info("TENGU V12 SQUAD_CRYPTO Starting — Token Scorer + Gem Scanner + Multi-TF")
    logger.info(f"Base symbols: {BASE_CRYPTO_SYMBOLS}")
    logger.info(f"Gem scan interval: every {GEM_SCAN_INTERVAL_CYCLES} cycles (~{GEM_SCAN_INTERVAL_CYCLES * 30 // 60} min)")
    schedule.every(30).seconds.do(autonomous_step)
    autonomous_step()
    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
