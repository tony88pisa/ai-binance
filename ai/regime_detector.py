"""
REGIME DETECTOR V8.3 — Module 6
Detects market regime (BULL / BEAR / SIDEWAYS) per-asset and globally.
Uses: ADX, RSI momentum clustering, volatility analysis, correlation.
"""
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime, timezone

logger = logging.getLogger("ai.regime_detector")


class MarketRegime:
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGING = "RANGING"
    CRASH = "CRASH"
    RECOVERY = "RECOVERY"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeSignal:
    """Result of regime detection for one asset."""
    asset: str
    regime: str = MarketRegime.UNKNOWN
    confidence: int = 0  # 0-100
    adx_value: float = 0.0
    rsi_slope: float = 0.0
    volatility_score: float = 0.0  # 0=calm, 1=extreme
    momentum_score: float = 0.0    # -1=bearish, +1=bullish
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "regime": self.regime,
            "confidence": self.confidence,
            "adx": round(self.adx_value, 2),
            "rsi_slope": round(self.rsi_slope, 3),
            "volatility": round(self.volatility_score, 3),
            "momentum": round(self.momentum_score, 3),
        }


@dataclass
class GlobalRegime:
    """Aggregated regime across all monitored pairs."""
    regime: str = MarketRegime.UNKNOWN
    confidence: int = 0
    bull_count: int = 0
    bear_count: int = 0
    sideways_count: int = 0
    avg_volatility: float = 0.0
    strategy_recommendation: str = "balanced"
    signals: List[RegimeSignal] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "confidence": self.confidence,
            "bull_count": self.bull_count,
            "bear_count": self.bear_count,
            "sideways_count": self.sideways_count,
            "avg_volatility": round(self.avg_volatility, 3),
            "strategy_rec": self.strategy_recommendation,
            "signals": [s.to_dict() for s in self.signals],
        }


class RegimeDetector:
    """
    Detects market regime using technical indicators.
    Works with pandas DataFrames from Freqtrade candles.
    """

    # ADX thresholds
    ADX_TREND_THRESHOLD = 25.0    # Above = trending
    ADX_STRONG_THRESHOLD = 40.0   # Above = strong trend

    # RSI boundaries
    RSI_BULL_ZONE = 55.0
    RSI_BEAR_ZONE = 45.0

    # Volatility (ATR-based) thresholds
    VOL_LOW = 0.3
    VOL_HIGH = 0.7

    def detect_asset_regime(self, df, pair: str) -> RegimeSignal:
        """Detect regime for a single asset using its candle DataFrame."""
        signal = RegimeSignal(asset=pair)

        if df is None or len(df) < 20:
            return signal

        try:
            close = df['close'].values.astype(float)
            high = df['high'].values.astype(float)
            low = df['low'].values.astype(float)

            # 1. ADX — Trend strength
            adx_val = self._compute_adx(high, low, close, period=14)
            signal.adx_value = adx_val

            # 2. RSI slope — Momentum direction
            rsi_vals = self._compute_rsi(close, period=14)
            if len(rsi_vals) >= 5:
                rsi_recent = rsi_vals[-5:]
                signal.rsi_slope = float(np.polyfit(range(len(rsi_recent)), rsi_recent, 1)[0])

            # 3. Volatility — ATR normalized
            atr = self._compute_atr(high, low, close, period=14)
            avg_price = np.mean(close[-14:]) if len(close) >= 14 else close[-1]
            signal.volatility_score = min(1.0, (atr / avg_price) * 100) if avg_price > 0 else 0.0

            # 4. Momentum composite
            ema_fast = self._ema(close, 8)
            ema_slow = self._ema(close, 21)
            if ema_slow != 0:
                signal.momentum_score = max(-1.0, min(1.0, (ema_fast - ema_slow) / ema_slow * 100))

            # 5. Classify regime
            current_rsi = rsi_vals[-1] if len(rsi_vals) > 0 else 50.0
            signal.regime, signal.confidence = self._classify(
                adx_val, current_rsi, signal.rsi_slope,
                signal.volatility_score, signal.momentum_score
            )

        except Exception as e:
            logger.error(f"Regime detection error [{pair}]: {e}")

        return signal

    def detect_global_regime(self, signals: List[RegimeSignal], external_data: Optional[Dict] = None) -> GlobalRegime:
        """
        Aggregate signals into a global market regime, incorporating external sentiment.
        external_data keys: 'fear_greed' (0-100), 'avg_funding' (float)
        """
        gr = GlobalRegime(signals=signals)
        if not signals:
            return gr

        gr.bull_count = sum(1 for s in signals if s.regime in [MarketRegime.BULL, MarketRegime.TREND_UP])
        gr.bear_count = sum(1 for s in signals if s.regime in [MarketRegime.BEAR, MarketRegime.TREND_DOWN])
        gr.sideways_count = sum(1 for s in signals if s.regime in [MarketRegime.SIDEWAYS, MarketRegime.RANGING])
        gr.avg_volatility = float(np.mean([s.volatility_score for s in signals]))

        # Calculate base regime from counts
        total = len(signals)
        dominant = MarketRegime.SIDEWAYS
        if gr.bull_count > total * 0.4: dominant = MarketRegime.BULL
        if gr.bear_count > total * 0.4: dominant = MarketRegime.BEAR

        # Refine with External Data (Phase 1 Module 11)
        fg_val = external_data.get("fear_greed", 50) if external_data else 50
        funding = external_data.get("avg_funding", 0.01) if external_data else 0.01

        # LOGIC: 
        # Extreme Fear + Low Vol + Recovery indicators = RECOVERY
        # Extreme Greed + Bull Count + Overheated Funding = CRASH WARNING or TREND_UP
        if fg_val < 20 and gr.avg_volatility < 0.3:
            gr.regime = MarketRegime.RECOVERY
            gr.strategy_recommendation = "accumulator"
        elif fg_val > 80 and funding > 0.03:
            gr.regime = MarketRegime.CRASH
            gr.strategy_recommendation = "conservative"
        elif dominant == MarketRegime.BULL:
            gr.regime = MarketRegime.TREND_UP if funding < 0.05 else MarketRegime.BULL
            gr.strategy_recommendation = "aggressive"
        elif dominant == MarketRegime.BEAR:
            gr.regime = MarketRegime.TREND_DOWN if funding < 0 else MarketRegime.BEAR
            gr.strategy_recommendation = "conservative"
        else:
            gr.regime = MarketRegime.RANGING if gr.avg_volatility < 0.4 else MarketRegime.SIDEWAYS
            gr.strategy_recommendation = "mean_reversion"

        gr.confidence = int(min(100, 50 + (gr.avg_volatility * 20)))
        return gr

    # === PRIVATE HELPERS ===

    def _classify(self, adx, rsi, rsi_slope, vol, momentum) -> tuple:
        """Returns (regime, confidence)."""
        trending = adx > self.ADX_TREND_THRESHOLD

        if trending:
            if rsi > self.RSI_BULL_ZONE and momentum > 0:
                conf = min(95, int(50 + adx + abs(momentum) * 10))
                return MarketRegime.BULL, conf
            elif rsi < self.RSI_BEAR_ZONE and momentum < 0:
                conf = min(95, int(50 + adx + abs(momentum) * 10))
                return MarketRegime.BEAR, conf

        # Low ADX or mixed signals = sideways
        conf = min(90, int(70 - adx))
        return MarketRegime.SIDEWAYS, max(30, conf)

    def _compute_rsi(self, close, period=14):
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.convolve(gains, np.ones(period)/period, mode='valid')
        avg_loss = np.convolve(losses, np.ones(period)/period, mode='valid')
        rs = np.divide(avg_gain, avg_loss, out=np.ones_like(avg_gain), where=avg_loss != 0)
        return 100 - (100 / (1 + rs))

    def _compute_adx(self, high, low, close, period=14):
        if len(close) < period * 2:
            return 0.0
        tr = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - close[:-1]),
                                   np.abs(low[1:] - close[:-1])))
        atr = np.mean(tr[-period:])
        if atr == 0:
            return 0.0
        plus_dm = np.where((high[1:] - high[:-1]) > (low[:-1] - low[1:]),
                           np.maximum(high[1:] - high[:-1], 0), 0)
        minus_dm = np.where((low[:-1] - low[1:]) > (high[1:] - high[:-1]),
                            np.maximum(low[:-1] - low[1:], 0), 0)
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr
        dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        return float(dx)

    def _compute_atr(self, high, low, close, period=14):
        if len(close) < period + 1:
            return 0.0
        tr = np.maximum(high[1:] - low[1:],
                        np.maximum(np.abs(high[1:] - close[:-1]),
                                   np.abs(low[1:] - close[:-1])))
        return float(np.mean(tr[-period:]))

    def _ema(self, data, period):
        if len(data) < period:
            return float(data[-1]) if len(data) > 0 else 0.0
        weights = np.exp(np.linspace(-1., 0., period))
        weights /= weights.sum()
        return float(np.convolve(data[-period*2:], weights, mode='valid')[-1])


# Strategy family mapping for NVIDIA Teacher integration
REGIME_STRATEGY_MAP = {
    MarketRegime.BULL: {
        "family": "NvidiaTeacher-Aggressive",
        "min_confidence": 50,
        "trailing_stop": True,
        "stoploss": -0.07,
    },
    MarketRegime.BEAR: {
        "family": "NvidiaTeacher-Conservative",
        "min_confidence": 75,
        "trailing_stop": True,
        "stoploss": -0.03,
    },
    MarketRegime.SIDEWAYS: {
        "family": "NvidiaTeacher-MeanReversion",
        "min_confidence": 60,
        "trailing_stop": False,
        "stoploss": -0.04,
    },
}
