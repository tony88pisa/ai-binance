"""
TENGU V11 — Technical Signal Engine (No-LLM Autonomous Trader)
=============================================================
Motore decisionale basato puramente su analisi tecnica.
Opera SENZA aspettare il verdetto dell'LLM quando i segnali sono chiari.

Strategie implementate (ispirate a progetti open-source validati):
1. RSI Mean Reversion  → Compra su ipervenduto, vendi su ipercomprato
2. MACD Crossover      → Conferma momentum con crossover signal line
3. Bollinger Squeeze   → Entra quando la volatilità esplode dopo compressione
4. DCA Smart           → Dollar Cost Averaging su drawdown tecnici
"""
import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger("technical_engine")


@dataclass
class TechnicalSignal:
    """Verdetto del motore tecnico."""
    action: str        # "BUY", "SELL", "HOLD"
    strategy: str      # nome della strategia che ha triggerato
    confidence: int    # 0-100
    reason: str
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


class TechnicalEngine:
    """
    Motore decisionale tecnico puro per micro-capitale.
    Ogni strategia vota indipendentemente; il consenso decide.
    """

    def __init__(self, risk_pct: float = 0.02, atr_sl_mult: float = 1.5, atr_tp_mult: float = 2.5):
        self.risk_pct = risk_pct          # 2% max per trade
        self.atr_sl_mult = atr_sl_mult    # Stop loss = 1.5x ATR
        self.atr_tp_mult = atr_tp_mult    # Take profit = 2.5x ATR (R:R = 1.67)

    # ── Indicatori ──
    @staticmethod
    def ema(data: np.ndarray, period: int) -> np.ndarray:
        alpha = 2.0 / (period + 1)
        result = np.empty_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    @staticmethod
    def rsi(closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    @staticmethod
    def bollinger_bands(closes: np.ndarray, period: int = 20, num_std: float = 2.0):
        if len(closes) < period:
            mid = closes[-1]
            return mid, mid, mid, 0.0
        window = closes[-period:]
        mid = float(np.mean(window))
        std = float(np.std(window))
        upper = mid + num_std * std
        lower = mid - num_std * std
        bandwidth = (upper - lower) / mid if mid > 0 else 0
        return mid, upper, lower, bandwidth

    @staticmethod
    def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 0.0
        trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
               for i in range(1, len(closes))]
        return float(np.mean(trs[-period:]))

    @staticmethod
    def macd_histogram(closes: np.ndarray):
        if len(closes) < 35:
            return 0.0, 0.0, 0.0
        ema12 = TechnicalEngine.ema(closes, 12)
        ema26 = TechnicalEngine.ema(closes, 26)
        macd_line = ema12 - ema26
        signal_line = TechnicalEngine.ema(macd_line, 9)
        histogram = macd_line - signal_line
        return float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1])

    # ── Strategie ──
    def strategy_rsi_mean_reversion(self, closes: np.ndarray, rsi_val: float) -> Optional[TechnicalSignal]:
        """
        RSI Mean Reversion: Compra quando RSI < 30 (ipervenduto), vendi quando RSI > 70.
        Su memecoin usiamo soglie più aggressive: RSI < 25 per BUY, > 75 per SELL.
        """
        price = float(closes[-1])

        if rsi_val <= 25:
            return TechnicalSignal(
                action="BUY", strategy="RSI_MEAN_REVERSION", confidence=75,
                reason=f"RSI={rsi_val:.0f} ipervenduto (soglia ≤25). Mean reversion probabile.",
                entry_price=price
            )
        elif rsi_val >= 75:
            return TechnicalSignal(
                action="SELL", strategy="RSI_MEAN_REVERSION", confidence=70,
                reason=f"RSI={rsi_val:.0f} ipercomprato (soglia ≥75). Reversal imminente."
            )
        return None

    def strategy_macd_crossover(self, closes: np.ndarray) -> Optional[TechnicalSignal]:
        """
        MACD Crossover: BUY quando la linea MACD incrocia sopra la signal line.
        Conferma: il crossover deve essere avvenuto nelle ultime 3 candele.
        """
        if len(closes) < 40:
            return None

        ema12 = self.ema(closes, 12)
        ema26 = self.ema(closes, 26)
        macd_line = ema12 - ema26
        signal_line = self.ema(macd_line, 9)

        # Crossover rialzista nelle ultime 3 candele
        for i in range(-3, 0):
            prev_idx = i - 1
            if prev_idx < -len(macd_line):
                continue
            if macd_line[prev_idx] < signal_line[prev_idx] and macd_line[i] > signal_line[i]:
                return TechnicalSignal(
                    action="BUY", strategy="MACD_CROSSOVER", confidence=65,
                    reason=f"MACD bullish crossover rilevato. Momentum in accelerazione.",
                    entry_price=float(closes[-1])
                )

        # Crossover ribassista
        for i in range(-3, 0):
            prev_idx = i - 1
            if prev_idx < -len(macd_line):
                continue
            if macd_line[prev_idx] > signal_line[prev_idx] and macd_line[i] < signal_line[i]:
                return TechnicalSignal(
                    action="SELL", strategy="MACD_CROSSOVER", confidence=60,
                    reason=f"MACD bearish crossover. Momentum in decelerazione."
                )

        return None

    def strategy_bollinger_squeeze(self, closes: np.ndarray) -> Optional[TechnicalSignal]:
        """
        Bollinger Squeeze: Quando la bandwidth si comprime sotto il 2% e poi espande,
        è segno di un breakout imminente. La direzione dipende dal prezzo vs banda media.
        """
        if len(closes) < 25:
            return None

        mid, upper, lower, bandwidth = self.bollinger_bands(closes)
        price = float(closes[-1])

        # Calcola bandwidth storica per confronto
        recent_bw = []
        for offset in range(5, 15):
            if offset > len(closes):
                break
            _, u, l, bw = self.bollinger_bands(closes[:-offset])
            recent_bw.append(bw)

        if not recent_bw:
            return None

        avg_bw = float(np.mean(recent_bw))

        # Squeeze: bandwidth attuale < 50% della media → compressione
        if bandwidth < avg_bw * 0.5 and bandwidth > 0:
            # Prezzo sotto la media → probabile rimbalzo verso l'alto
            if price < mid:
                return TechnicalSignal(
                    action="BUY", strategy="BOLLINGER_SQUEEZE", confidence=60,
                    reason=f"Bollinger Squeeze attivo (BW={bandwidth:.4f} vs avg={avg_bw:.4f}). Prezzo sotto media → breakout rialzista probabile.",
                    entry_price=price
                )
        # Breakout: prezzo oltre la banda superiore con espansione
        elif price > upper and bandwidth > avg_bw * 1.5:
            return TechnicalSignal(
                action="SELL", strategy="BOLLINGER_SQUEEZE", confidence=55,
                reason=f"Prezzo oltre Bollinger Upper ({upper:.8f}). Overbought temporaneo."
            )

        return None

    # ── Consenso Multi-Strategia ──
    def evaluate(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> TechnicalSignal:
        """
        Esegue tutte le strategie e ritorna il consenso.
        Logica: se almeno 2 strategie su 3 concordano → azione.
        Se solo 1 → HOLD (serve conferma).
        """
        price = float(closes[-1])
        rsi_val = self.rsi(closes)
        current_atr = self.atr(highs, lows, closes)

        # Raccogli voti
        votes: List[TechnicalSignal] = []

        s1 = self.strategy_rsi_mean_reversion(closes, rsi_val)
        if s1:
            votes.append(s1)

        s2 = self.strategy_macd_crossover(closes)
        if s2:
            votes.append(s2)

        s3 = self.strategy_bollinger_squeeze(closes)
        if s3:
            votes.append(s3)

        # Nessun segnale
        if not votes:
            return TechnicalSignal(
                action="HOLD", strategy="CONSENSUS", confidence=0,
                reason=f"Nessuna strategia ha generato segnali. RSI={rsi_val:.0f}, ATR={current_atr:.8f}"
            )

        # Conta i voti per azione
        buy_votes = [v for v in votes if v.action == "BUY"]
        sell_votes = [v for v in votes if v.action == "SELL"]

        if len(buy_votes) >= 2:
            # Consenso BUY: media delle confidence
            avg_conf = int(np.mean([v.confidence for v in buy_votes]))
            strategies = " + ".join([v.strategy for v in buy_votes])
            sl = price - (current_atr * self.atr_sl_mult) if current_atr > 0 else price * 0.97
            tp = price + (current_atr * self.atr_tp_mult) if current_atr > 0 else price * 1.05
            return TechnicalSignal(
                action="BUY", strategy=f"CONSENSUS({strategies})", confidence=avg_conf,
                reason=f"Consenso BUY da {len(buy_votes)} strategie: {strategies}. RSI={rsi_val:.0f}",
                entry_price=price, stop_loss=sl, take_profit=tp
            )

        if len(sell_votes) >= 2:
            avg_conf = int(np.mean([v.confidence for v in sell_votes]))
            strategies = " + ".join([v.strategy for v in sell_votes])
            return TechnicalSignal(
                action="SELL", strategy=f"CONSENSUS({strategies})", confidence=avg_conf,
                reason=f"Consenso SELL da {len(sell_votes)} strategie: {strategies}."
            )

        # Solo 1 voto → serve conferma forte (confidence > 70)
        best = max(votes, key=lambda v: v.confidence)
        if best.confidence >= 70:
            if best.action == "BUY":
                sl = price - (current_atr * self.atr_sl_mult) if current_atr > 0 else price * 0.97
                tp = price + (current_atr * self.atr_tp_mult) if current_atr > 0 else price * 1.05
                best.stop_loss = sl
                best.take_profit = tp
            return best

        return TechnicalSignal(
            action="HOLD", strategy="CONSENSUS", confidence=best.confidence,
            reason=f"Segnale singolo ({best.strategy}) con conf={best.confidence}% — insufficiente per consenso. RSI={rsi_val:.0f}"
        )
