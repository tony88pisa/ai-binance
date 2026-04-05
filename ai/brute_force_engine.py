import numpy as np
from itertools import product
import logging
import time

logger = logging.getLogger("ai.brute_force_engine")

class BruteForceEngine:
    def __init__(self, max_drawdown_limit: float = -0.10):
        # Parametro utente: Massima tolleranza drawdown impostata a -10% per test limitato ma profittevole
        self.max_drawdown_limit = max_drawdown_limit
        
    def _compute_rsi(self, closes: np.ndarray, period: int = 14) -> np.ndarray:
        deltas = np.diff(closes)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        
        res = np.zeros_like(closes)
        res[:period] = 100. - 100. / (1. + rs)
        
        for i in range(period, len(closes)):
            delta = deltas[i - 1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
                
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down if down != 0 else 0
            res[i] = 100. - 100. / (1. + rs)
            
        return res

    def _compute_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period=14) -> np.ndarray:
        atr = np.zeros_like(closes)
        if len(closes) < period + 1: return atr
        
        tr = np.zeros_like(closes)
        tr[0] = highs[0] - lows[0]
        for i in range(1, len(closes)):
            tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
            
        # SMA for the first ATR
        atr[period] = np.mean(tr[1:period+1])
        # EMA smoothing
        for i in range(period+1, len(closes)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
            
        return atr

    def _compute_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average vettoriale."""
        ema = np.zeros_like(data)
        if len(data) < period: return ema
        ema[period - 1] = np.mean(data[:period])
        multiplier = 2.0 / (period + 1)
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema

    def _compute_volume_ratio(self, volumes: np.ndarray, period: int = 20) -> np.ndarray:
        """Rapporto Volume Corrente / Media Volume (spike detector)."""
        ratio = np.ones_like(volumes)
        for i in range(period, len(volumes)):
            avg = np.mean(volumes[i-period:i])
            ratio[i] = volumes[i] / avg if avg > 0 else 1.0
        return ratio

    def _compute_sortino_ratio(self, returns: list, target: float = 0.0) -> float:
        """Sortino Ratio: penalizza solo le escursioni NEGATIVE.
        Il paper prescrive di ottimizzare per avversione al ribasso, non rendimento lordo."""
        if not returns:
            return 0.0
        excess = [r - target for r in returns]
        mean_excess = np.mean(excess)
        downside = [min(0, r - target) ** 2 for r in returns]
        downside_dev = np.sqrt(np.mean(downside)) if downside else 1.0
        if downside_dev == 0:
            return mean_excess * 10  # Nessun ribasso: score altissimo
        return mean_excess / downside_dev

    def _compute_fractional_kelly(self, returns: list, fraction: float = 0.25) -> float:
        """Fractional Kelly Criterion: calcola la dimensione ottimale della scommessa.
        f* = (p * b - q) / b   con p=prob vittoria, b=rapporto vincita/perdita, q=1-p
        Usiamo una frazione conservativa (25%) come suggerisce il paper."""
        if not returns:
            return 0.0
        wins = [r for r in returns if r > 0]
        losses = [abs(r) for r in returns if r < 0]
        if not wins or not losses:
            return 0.05  # Fallback minimo
        p = len(wins) / len(returns)
        q = 1 - p
        avg_win = np.mean(wins)
        avg_loss = np.mean(losses)
        b = avg_win / avg_loss if avg_loss > 0 else 1.0
        kelly_full = (p * b - q) / b if b > 0 else 0.0
        kelly_frac = max(0.01, min(kelly_full * fraction, 0.30))  # Clamp 1%-30%
        return kelly_frac
            
    def evaluate_variants(self, klines: list, base_skill: dict) -> dict:
        """
        Riceve Klines raw da Binance e testa varianti parametriche.
        klines: [ [open_time, open, high, low, close...], ... ]
        """
        if not klines or len(klines) < 100:
            return {"passed": False, "reason": "Insufficient data"}
            
        t0 = time.time()
        
        # Pre-processamento vettoriale ultra veloce
        closes = np.array([float(k[4]) for k in klines])
        highs = np.array([float(k[2]) for k in klines])
        lows = np.array([float(k[3]) for k in klines])
        volumes = np.array([float(k[5]) for k in klines])
        
        # Pre-computiamo gli indicatori sull'intero dataset (evita di ricalcolarli per ogni variante)
        logger.info("Computing indicators for full dataset (RSI, ATR, EMA, Volume)...")
        rsi_14 = self._compute_rsi(closes)
        atr_14 = self._compute_atr(highs, lows, closes)
        ema_fast = self._compute_ema(closes, 9)
        ema_slow = self._compute_ema(closes, 21)
        vol_ratio = self._compute_volume_ratio(volumes)
        
        # Griglie dei parametri (espansa con filtro volume)
        rsi_entry_range = [20, 25, 30, 35, 40]
        rsi_exit_range = [60, 65, 70, 75, 80]
        atr_stop_range = [1.5, 2.0, 3.0, 4.0]
        tp_pct_range = [0.03, 0.05, 0.08, 0.15]
        volume_min_ratio = [0.0, 1.2, 1.5]  # 0.0 = no filter, 1.2 = require 20% above avg

        
        best_variant = None
        best_objective = -999.0
        
        total_variants = len(rsi_entry_range) * len(rsi_exit_range) * len(atr_stop_range) * len(tp_pct_range) * len(volume_min_ratio)
        logger.info(f"Simulating {total_variants} parameter variants (Brute Force Mode V2 + EMA + Volume)...")
        
        for rsi_buy, rsi_sell, atr_stop, tp_pct, vol_min in product(rsi_entry_range, rsi_exit_range, atr_stop_range, tp_pct_range, volume_min_ratio):
            # Simulation fast-loop su questo dataset
            in_position = False
            entry_price = 0.0
            stop_loss = 0.0
            take_profit = 0.0
            
            pnl_pct_history = []
            
            for i in range(21, len(closes)):
                cur_close = closes[i]
                cur_rsi = rsi_14[i]
                cur_atr = atr_14[i]
                cur_low = lows[i]
                cur_high = highs[i]
                
                if not in_position:
                    # Entry: RSI oversold + optional volume spike + EMA trend confirmation
                    ema_bullish = ema_fast[i] > ema_slow[i]
                    volume_ok = vol_ratio[i] >= vol_min if vol_min > 0 else True
                    if cur_rsi < rsi_buy and ema_bullish and volume_ok:
                        in_position = True
                        entry_price = cur_close
                        stop_loss = entry_price - (cur_atr * atr_stop)
                        take_profit = entry_price * (1.0 + tp_pct)
                else:
                    # Exit logic
                    pnl = 0.0
                    if cur_low <= stop_loss:
                        # Stoppato
                        pnl = (stop_loss - entry_price) / entry_price
                        pnl_pct_history.append(pnl)
                        in_position = False
                    elif cur_high >= take_profit:
                        # Take Profit colpito
                        pnl = (take_profit - entry_price) / entry_price
                        pnl_pct_history.append(pnl)
                        in_position = False
                    elif cur_rsi > rsi_sell:
                        # Exit dinamico per indicatore
                        pnl = (cur_close - entry_price) / entry_price
                        pnl_pct_history.append(pnl)
                        in_position = False
                        
            # Analisi della variante
            if not pnl_pct_history:
                continue
                
            wins = sum(1 for p in pnl_pct_history if p > 0)
            total_trades = len(pnl_pct_history)
            win_rate = (wins / total_trades) * 100.0
            cum_pnl = sum(pnl_pct_history)
            
            # Drawdown calcolato sull'equity cumulativa iterativa
            equity = 1.0
            peak = 1.0
            true_max_dd = 0.0
            for p in pnl_pct_history:
                equity *= (1.0 + p)
                if equity > peak:
                    peak = equity
                dd = (equity - peak) / peak
                if dd < true_max_dd:
                    true_max_dd = dd
                    
            # Filtro del Risk Management Rigido: Scarta istantaneamente se DD supera -10% tollerato
            if true_max_dd < self.max_drawdown_limit:
                continue
                
            # Se passa il filtro del drawdown, valutiamo con SORTINO + FRACTIONAL KELLY
            # Il paper prescrive: NON massimizzare rendimento lordo, ma Sortino Ratio
            sortino = self._compute_sortino_ratio(pnl_pct_history)
            kelly_f = self._compute_fractional_kelly(pnl_pct_history)
            
            if total_trades > 3 and win_rate > 50:
                objective = sortino * (win_rate / 100.0)
            else:
                objective = -1.0
                
            if objective > best_objective:
                best_objective = objective
                best_variant = {
                    "rsi_buy": rsi_buy,
                    "rsi_sell": rsi_sell,
                    "atr_stop_multiplier": atr_stop,
                    "take_profit_pct": tp_pct,
                    "volume_min_ratio": vol_min,
                    "ema_filter": True,
                    "kelly_fraction": round(kelly_f, 4),
                    "metrics": {
                        "total_trades": total_trades,
                        "win_rate": round(win_rate, 2),
                        "net_pnl_pct": round(cum_pnl * 100, 2),
                        "max_drawdown_pct": round(true_max_dd * 100, 2),
                        "sortino_ratio": round(sortino, 4),
                        "kelly_optimal_size": round(kelly_f * 100, 2),
                        "objective_score": round(objective, 4)
                    }
                }
                
        duration = time.time() - t0
        logger.info(f"Brute Force Simulator V2 completato in {duration:.2f} sec.")
        
        if best_variant and best_variant["metrics"]["net_pnl_pct"] > 0:
            logger.info(f"🏆 BEST VARIANT WINNER: PnL: {best_variant['metrics']['net_pnl_pct']}% | DD: {best_variant['metrics']['max_drawdown_pct']}%")
            
            # Promuovi e costruisci la nuova formula magica ottimizzata
            params = best_variant
            vol_part = f" VOL_MIN: {params['volume_min_ratio']}x avg." if params['volume_min_ratio'] > 0 else ""
            rule = f"RULE (BRUTE-FORCED V2): BUY when RSI < {params['rsi_buy']} AND EMA9 > EMA21{vol_part}. SELL when RSI > {params['rsi_sell']}. STOP: {params['atr_stop_multiplier']}x ATR. TP: {params['take_profit_pct']*100}%"
            
            return {
                "passed": True,
                "optimized_params": best_variant,
                "prompt_rule": rule,
                "reason": "Brute Force found optimal parameters passing max DD constraints."
            }
        else:
            return {
                "passed": False,
                "reason": "No profitable parameters found within drawdown limits."
            }
