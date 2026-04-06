"""
TENGU V12 — BACKTESTER
========================
Ispirato da: backtesting-frameworks (antigravity-awesome-skills)

Framework di backtesting offline per validare parametri della strategia
(soglie RSI, ATR multiplier, Kelly bounds) prima di modificarli nel live.

Caratteristiche:
  - Walk-forward: train 70% / validate 15% / test 15%
  - Simula scoring + technical analysis + position management
  - Calcola: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor
  - Output JSON report
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai.technical_engine import TechnicalEngine
from ai.token_scorer import TokenScorer

logger = logging.getLogger("backtester")


# ──────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ──────────────────────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    """Configurazione del backtest."""
    symbol: str = "PEPE/USDT"
    timeframe: str = "5m"
    initial_capital: float = 100.0
    min_score: int = 70               # Min token score per entrare
    min_confidence: int = 70          # Min confidence per comprare
    max_open_trades: int = 1          # Per semplicità backtest
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.5
    trailing_atr_mult: float = 1.0
    position_size_pct: float = 0.15   # 15% del capitale per trade
    use_multi_timeframe: bool = True
    walk_forward: bool = True         # Abilita walk-forward split


@dataclass
class TradeResult:
    """Singolo trade completato nel backtest."""
    symbol: str
    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    reason: str                       # "STOP_LOSS" | "TAKE_PROFIT" | "TRAILING" | "END"
    token_score: int = 0
    entry_rsi: float = 0
    holding_bars: int = 0


@dataclass 
class BacktestReport:
    """Report completo del backtest."""
    symbol: str
    timeframe: str
    period: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    avg_trade_pnl_pct: float
    avg_holding_bars: float
    best_trade_pct: float
    worst_trade_pct: float
    trades: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["trades"] = [asdict(t) for t in self.trades]
        return d
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def print_summary(self) -> None:
        """Stampa un riepilogo formattato del backtest."""
        print("\n" + "=" * 60)
        print(f"  TENGU V12 BACKTEST REPORT — {self.symbol}")
        print("=" * 60)
        print(f"  Periodo:          {self.period}")
        print(f"  Timeframe:        {self.timeframe}")
        print(f"  Capitale iniziale: ${self.initial_capital:.2f}")
        print(f"  Capitale finale:   ${self.final_capital:.2f}")
        print(f"  Return totale:     {self.total_return_pct:+.2f}%")
        print("-" * 60)
        print(f"  Trade totali:      {self.total_trades}")
        print(f"  Vincenti:          {self.winning_trades} ({self.win_rate:.1f}%)")
        print(f"  Perdenti:          {self.losing_trades}")
        print(f"  Profit Factor:     {self.profit_factor:.2f}")
        print(f"  Media PnL/trade:   {self.avg_trade_pnl_pct:+.2f}%")
        print("-" * 60)
        print(f"  Sharpe Ratio:      {self.sharpe_ratio:.3f}")
        print(f"  Sortino Ratio:     {self.sortino_ratio:.3f}")
        print(f"  Max Drawdown:      {self.max_drawdown_pct:.2f}%")
        print("-" * 60)
        print(f"  Miglior trade:     {self.best_trade_pct:+.2f}%")
        print(f"  Peggior trade:     {self.worst_trade_pct:+.2f}%")
        print(f"  Media holding:     {self.avg_holding_bars:.0f} barre")
        print("=" * 60)
        
        # Verdetto
        if self.total_return_pct > 5 and self.win_rate > 50 and self.max_drawdown_pct > -15:
            print("  [GREEN] VERDETTO: STRATEGIA PROMETTENTE")
        elif self.total_return_pct > 0 and self.win_rate > 40:
            print("  [YELLOW] VERDETTO: STRATEGIA MARGINALE -- richiede tuning")
        else:
            print("  [RED] VERDETTO: STRATEGIA NON PROFITTEVOLE -- non usare in live")
        print()


# ──────────────────────────────────────────────────────────────────
# BACKTESTER ENGINE
# ──────────────────────────────────────────────────────────────────

class Backtester:
    """
    Simulatore di trading offline.
    Replay dei dati storici con la stessa logica di squad_crypto.
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.scorer = TokenScorer()

    def run(self, df: pd.DataFrame) -> BacktestReport:
        """
        Esegue il backtest su un DataFrame OHLCV.
        
        Args:
            df: DataFrame con colonne [timestamp, open, high, low, close, volume]
            
        Returns:
            BacktestReport con metriche complete
        """
        config = self.config
        
        if len(df) < 100:
            raise ValueError(f"Dati insufficienti: {len(df)} candele (minimo 100)")
        
        # Walk-forward split
        if config.walk_forward:
            n = len(df)
            train_end = int(n * 0.70)
            val_end = int(n * 0.85)
            
            # Usa la sezione di test per il report finale
            test_df = df.iloc[val_end:].copy().reset_index(drop=True)
            period = f"Test split ({n - val_end} candele su {n} totali)"
            logger.info(f"Walk-forward: Train={train_end}, Val={val_end - train_end}, Test={n - val_end}")
        else:
            test_df = df.copy().reset_index(drop=True)
            period = f"Full ({len(df)} candele)"
        
        # Simulazione
        trades = self._simulate(test_df)
        
        # Calcolo metriche
        report = self._compute_metrics(trades, test_df, period)
        return report

    def _simulate(self, df: pd.DataFrame) -> list[TradeResult]:
        """Simula la strategia su dati storici."""
        config = self.config
        trades: list[TradeResult] = []
        
        capital = config.initial_capital
        position = None  # Dict con entry info quando aperta
        
        # Pre-calcola indicatori
        import pandas_ta as ta
        df = df.copy()
        df['rsi'] = ta.rsi(df['close'], length=14)
        macd_df = ta.macd(df['close'])
        df['macd'] = macd_df['MACD_12_26_9']
        df['macd_s'] = macd_df['MACDs_12_26_9']
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['ema200'] = ta.ema(df['close'], length=200)
        
        # Sliding window per scoring
        LOOKBACK = 50
        
        for i in range(LOOKBACK, len(df)):
            price = float(df['close'].iloc[i])
            rsi = float(df['rsi'].iloc[i]) if not pd.isna(df['rsi'].iloc[i]) else 50
            macd_val = float(df['macd'].iloc[i]) if not pd.isna(df['macd'].iloc[i]) else 0
            macd_s = float(df['macd_s'].iloc[i]) if not pd.isna(df['macd_s'].iloc[i]) else 0
            atr = float(df['atr'].iloc[i]) if not pd.isna(df['atr'].iloc[i]) else price * 0.02
            
            # === GESTIONE POSIZIONE APERTA ===
            if position is not None:
                # Check trailing
                if not position["trailing_on"] and price >= position["trailing_activation"]:
                    position["trailing_on"] = True
                
                if position["trailing_on"]:
                    candidate_sl = price * 0.985
                    if candidate_sl > position["sl"]:
                        position["sl"] = candidate_sl
                
                # Check exit
                reason = None
                if price <= position["sl"]:
                    reason = "STOP_LOSS"
                elif price >= position["tp"]:
                    reason = "TAKE_PROFIT"
                
                if reason:
                    pnl_pct = (price - position["entry_price"]) / position["entry_price"] * 100
                    pnl_usd = position["size_usd"] * (pnl_pct / 100)
                    capital += position["size_usd"] + pnl_usd
                    
                    trades.append(TradeResult(
                        symbol=config.symbol,
                        entry_idx=position["entry_idx"],
                        exit_idx=i,
                        entry_price=position["entry_price"],
                        exit_price=price,
                        pnl_pct=round(pnl_pct, 4),
                        pnl_usd=round(pnl_usd, 4),
                        reason=reason,
                        token_score=position.get("score", 0),
                        entry_rsi=position.get("entry_rsi", 0),
                        holding_bars=i - position["entry_idx"],
                    ))
                    position = None
                continue
            
            # === SEGNALE DI ENTRY ===
            if position is None:
                # Score token (usando sliding window)
                window_df = df.iloc[max(0, i - LOOKBACK):i + 1].copy().reset_index(drop=True)
                score = self.scorer.score(config.symbol, window_df)
                
                if not score.is_tradeable:
                    continue
                
                # Check condizioni tecniche (simula decision_engine semplificato)
                buy_signal = False
                confidence = 50
                
                if rsi < 30 and macd_val > macd_s:
                    buy_signal = True
                    confidence = 80
                elif rsi < 40 and macd_val > macd_s and macd_val > 0:
                    buy_signal = True
                    confidence = 65
                
                if not buy_signal or confidence < config.min_confidence:
                    continue
                
                # Calcola livelli
                levels = TechnicalEngine.get_stop_levels(price, atr, side="long")
                size_usd = capital * config.position_size_pct
                
                if size_usd > capital:
                    continue
                
                capital -= size_usd
                position = {
                    "entry_idx": i,
                    "entry_price": price,
                    "size_usd": size_usd,
                    "sl": levels["sl"],
                    "tp": levels["tp"],
                    "trailing_activation": levels["trailing_activation"],
                    "trailing_on": False,
                    "score": score.total,
                    "entry_rsi": rsi,
                }
        
        # Chiudi posizione rimasta aperta alla fine
        if position is not None:
            price = float(df['close'].iloc[-1])
            pnl_pct = (price - position["entry_price"]) / position["entry_price"] * 100
            pnl_usd = position["size_usd"] * (pnl_pct / 100)
            capital += position["size_usd"] + pnl_usd
            trades.append(TradeResult(
                symbol=config.symbol,
                entry_idx=position["entry_idx"],
                exit_idx=len(df) - 1,
                entry_price=position["entry_price"],
                exit_price=price,
                pnl_pct=round(pnl_pct, 4),
                pnl_usd=round(pnl_usd, 4),
                reason="END",
                token_score=position.get("score", 0),
                entry_rsi=position.get("entry_rsi", 0),
                holding_bars=len(df) - 1 - position["entry_idx"],
            ))
        
        return trades

    def _compute_metrics(self, trades: list[TradeResult], df: pd.DataFrame, period: str) -> BacktestReport:
        """Calcola tutte le metriche dal risultato del backtest."""
        config = self.config
        
        if not trades:
            return BacktestReport(
                symbol=config.symbol, timeframe=config.timeframe, period=period,
                initial_capital=config.initial_capital, final_capital=config.initial_capital,
                total_return_pct=0, total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0, profit_factor=0, sharpe_ratio=0, sortino_ratio=0,
                max_drawdown_pct=0, avg_trade_pnl_pct=0, avg_holding_bars=0,
                best_trade_pct=0, worst_trade_pct=0, trades=trades,
            )
        
        pnls = [t.pnl_pct for t in trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]
        
        # Equity curve per drawdown
        equity = [config.initial_capital]
        for t in trades:
            equity.append(equity[-1] + t.pnl_usd)
        
        equity_arr = np.array(equity)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (equity_arr - peak) / peak * 100
        max_dd = float(drawdown.min())
        
        # Sharpe & Sortino (annualizzato, assumendo ~100 trade/anno)
        pnl_arr = np.array(pnls)
        avg_return = float(np.mean(pnl_arr))
        std_return = float(np.std(pnl_arr)) if len(pnl_arr) > 1 else 1
        downside_std = float(np.std(pnl_arr[pnl_arr < 0])) if len(pnl_arr[pnl_arr < 0]) > 1 else 1
        
        sharpe = (avg_return / std_return * np.sqrt(100)) if std_return > 0 else 0
        sortino = (avg_return / downside_std * np.sqrt(100)) if downside_std > 0 else 0
        
        # Profit Factor
        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999
        
        win_rate = (len(winners) / len(trades) * 100) if trades else 0
        
        return BacktestReport(
            symbol=config.symbol,
            timeframe=config.timeframe,
            period=period,
            initial_capital=config.initial_capital,
            final_capital=round(equity[-1], 4),
            total_return_pct=round((equity[-1] - config.initial_capital) / config.initial_capital * 100, 4),
            total_trades=len(trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 4),
            sharpe_ratio=round(float(sharpe), 4),
            sortino_ratio=round(float(sortino), 4),
            max_drawdown_pct=round(max_dd, 4),
            avg_trade_pnl_pct=round(avg_return, 4),
            avg_holding_bars=round(float(np.mean([t.holding_bars for t in trades])), 1),
            best_trade_pct=round(max(pnls), 4),
            worst_trade_pct=round(min(pnls), 4),
            trades=trades,
        )


# ──────────────────────────────────────────────────────────────────
# HELPER: FETCH HISTORICAL DATA
# ──────────────────────────────────────────────────────────────────

def fetch_historical_ohlcv(
    symbol: str,
    timeframe: str = "5m",
    days: int = 30,
    exchange_name: str = "binance",
) -> pd.DataFrame:
    """
    Scarica dati OHLCV storici via ccxt con paginazione.
    
    Args:
        symbol: Es. "PEPE/USDT"
        timeframe: Es. "5m", "1h"
        days: Numero di giorni di storia
        exchange_name: Nome exchange ccxt
    
    Returns:
        DataFrame con colonne [timestamp, open, high, low, close, volume]
    """
    import ccxt
    
    exchange_class = getattr(ccxt, exchange_name, ccxt.binance)
    exchange = exchange_class({"enableRateLimit": True})
    
    # Calcola millisecondi per barra
    tf_ms = {
        "1m": 60_000, "3m": 180_000, "5m": 300_000,
        "15m": 900_000, "30m": 1_800_000,
        "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
    }
    bar_ms = tf_ms.get(timeframe, 300_000)
    
    total_bars = int(days * 24 * 3_600_000 / bar_ms)
    since = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)
    
    all_data = []
    limit = 1000
    
    logger.info(f"Fetching {total_bars} bars of {symbol} {timeframe} (last {days} days)...")
    
    while len(all_data) < total_bars:
        try:
            data = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if not data:
                break
            all_data.extend(data)
            since = data[-1][0] + bar_ms
            if len(data) < limit:
                break
        except Exception as e:
            logger.error(f"Errore fetch OHLCV: {e}")
            break
    
    if not all_data:
        raise ValueError(f"Nessun dato scaricato per {symbol}")
    
    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    
    logger.info(f"Scaricati {len(df)} barre per {symbol}")
    return df
