"""
TENGU V12 — TOKEN SCORING ENGINE
==================================
Ispirato da: crypto-bd-agent (antigravity-awesome-skills)

Valuta ogni coin su 6 fattori ponderati (0-100) PRIMA di chiamare l'AI.
Coins con score < 70 vengono skippate → risparmio token LLM + meno trade spazzatura.

Fattori:
  1. Volume 24h        (25%) — liquidità e interesse di mercato
  2. Spread Bid/Ask    (20%) — costo implicito di esecuzione
  3. Trend Momentum    (20%) — allineamento indicatori tecnici
  4. Volatilità ATR    (15%) — sweet-spot di volatilità (non troppa, non poca)
  5. Volume Profile    (10%) — volume in crescita vs in calo
  6. Price Action      (10%) — distanza da supporto/resistenza
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("token_scorer")


# ──────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ──────────────────────────────────────────────────────────────────

@dataclass
class TokenScore:
    """Risultato strutturato dello scoring di un token."""
    symbol: str
    total: int                       # 0-100 score finale
    action: str                      # HOT | QUALIFIED | WATCH | SKIP
    breakdown: Dict[str, int] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_tradeable(self) -> bool:
        return self.total >= 70


def _classify_action(score: int) -> str:
    if score >= 85:
        return "HOT"
    elif score >= 70:
        return "QUALIFIED"
    elif score >= 50:
        return "WATCH"
    return "SKIP"


# ──────────────────────────────────────────────────────────────────
# SCORING ENGINE
# ──────────────────────────────────────────────────────────────────

class TokenScorer:
    """
    Motore di scoring multi-fattore per crypto tokens.
    Ogni fattore produce un sub-score 0-100 che viene poi pesato.
    """

    # Pesi per ogni fattore (totale = 1.0)
    WEIGHTS = {
        "volume_24h": 0.25,
        "spread": 0.20,
        "momentum": 0.20,
        "volatility": 0.15,
        "volume_profile": 0.10,
        "price_action": 0.10,
    }

    def score(
        self,
        symbol: str,
        df: pd.DataFrame,
        ticker: Optional[dict] = None,
    ) -> TokenScore:
        """
        Calcola lo score complessivo per un token.

        Args:
            symbol: Simbolo della coppia (es. "PEPE/USDT")
            df: DataFrame OHLCV con colonne [timestamp, open, high, low, close, volume]
            ticker: Dict dal fetch_ticker() di ccxt (opzionale, per bid/ask spread)

        Returns:
            TokenScore con punteggio 0-100 e breakdown dettagliato
        """
        reasons = []
        breakdown = {}

        try:
            # 1. Volume 24h Score
            vol_score, vol_reason = self._score_volume_24h(df, ticker)
            breakdown["volume_24h"] = vol_score
            reasons.append(vol_reason)

            # 2. Spread Score
            spread_score, spread_reason = self._score_spread(ticker)
            breakdown["spread"] = spread_score
            reasons.append(spread_reason)

            # 3. Momentum Score (RSI + MACD alignment)
            mom_score, mom_reason = self._score_momentum(df)
            breakdown["momentum"] = mom_score
            reasons.append(mom_reason)

            # 4. Volatility Sweet-Spot
            vol_ss_score, vol_ss_reason = self._score_volatility(df)
            breakdown["volatility"] = vol_ss_score
            reasons.append(vol_ss_reason)

            # 5. Volume Profile (crescente vs calante)
            vp_score, vp_reason = self._score_volume_profile(df)
            breakdown["volume_profile"] = vp_score
            reasons.append(vp_reason)

            # 6. Price Action (supporto/resistenza)
            pa_score, pa_reason = self._score_price_action(df)
            breakdown["price_action"] = pa_score
            reasons.append(pa_reason)

            # Calcolo score finale pesato
            total = sum(
                breakdown[k] * self.WEIGHTS[k] for k in self.WEIGHTS
            )
            total = int(round(total))

            action = _classify_action(total)

            logger.info(
                f"[SCORER] {symbol}: {total}/100 ({action}) | "
                f"Vol={breakdown['volume_24h']} Spread={breakdown['spread']} "
                f"Mom={breakdown['momentum']} Volat={breakdown['volatility']} "
                f"VProf={breakdown['volume_profile']} PA={breakdown['price_action']}"
            )

            return TokenScore(
                symbol=symbol,
                total=total,
                action=action,
                breakdown=breakdown,
                reasons=[r for r in reasons if r],
            )

        except Exception as e:
            logger.error(f"[SCORER] Errore scoring {symbol}: {e}")
            return TokenScore(
                symbol=symbol, total=0, action="SKIP",
                reasons=[f"Scoring error: {e}"]
            )

    # ── Fattore 1: Volume 24h ────────────────────────────────────

    def _score_volume_24h(self, df: pd.DataFrame, ticker: Optional[dict]) -> tuple[int, str]:
        """
        Volume 24h in USD.
        > $2M = 100,  $1M-2M = 85,  $500K-1M = 70,  $100K-500K = 45,  < $100K = 15
        """
        try:
            if ticker and ticker.get("quoteVolume"):
                vol_usd = float(ticker["quoteVolume"])
            else:
                # Stima volume dalle ultime 288 candele 5m (= 24h)
                recent = df.tail(288)
                vol_usd = float((recent["close"] * recent["volume"]).sum())

            if vol_usd >= 2_000_000:
                return 100, f"Vol24h ${vol_usd/1e6:.1f}M (eccellente)"
            elif vol_usd >= 1_000_000:
                return 85, f"Vol24h ${vol_usd/1e6:.1f}M (buono)"
            elif vol_usd >= 500_000:
                return 70, f"Vol24h ${vol_usd/1e3:.0f}K (accettabile)"
            elif vol_usd >= 100_000:
                return 45, f"Vol24h ${vol_usd/1e3:.0f}K (basso)"
            else:
                return 15, f"Vol24h ${vol_usd/1e3:.0f}K (pericolosamente basso)"
        except Exception:
            return 30, "Volume 24h non calcolabile"

    # ── Fattore 2: Spread Bid/Ask ────────────────────────────────

    def _score_spread(self, ticker: Optional[dict]) -> tuple[int, str]:
        """
        Spread bid/ask come % del prezzo medio.
        < 0.1% = 100,  0.1-0.3% = 80,  0.3-0.6% = 55,  0.6-1% = 30,  > 1% = 10
        """
        if not ticker or not ticker.get("bid") or not ticker.get("ask"):
            return 50, "Spread non disponibile (ticker mancante)"

        try:
            bid = float(ticker["bid"])
            ask = float(ticker["ask"])
            if bid <= 0 or ask <= 0:
                return 30, "Spread non calcolabile (prezzo zero)"

            mid = (bid + ask) / 2
            spread_pct = ((ask - bid) / mid) * 100

            if spread_pct < 0.1:
                return 100, f"Spread {spread_pct:.3f}% (eccellente)"
            elif spread_pct < 0.3:
                return 80, f"Spread {spread_pct:.3f}% (buono)"
            elif spread_pct < 0.6:
                return 55, f"Spread {spread_pct:.3f}% (medio)"
            elif spread_pct < 1.0:
                return 30, f"Spread {spread_pct:.3f}% (alto)"
            else:
                return 10, f"Spread {spread_pct:.3f}% (pericoloso)"
        except Exception:
            return 40, "Errore calcolo spread"

    # ── Fattore 3: Momentum ──────────────────────────────────────

    def _score_momentum(self, df: pd.DataFrame) -> tuple[int, str]:
        """
        Convergenza RSI + MACD + trend direction.
        Tutti bullish = 100, misti = 50, tutti bearish = 10
        """
        try:
            import pandas_ta as ta
            close = df["close"]

            rsi = ta.rsi(close, length=14)
            macd_df = ta.macd(close)

            if rsi is None or macd_df is None:
                return 40, "Indicatori momentum insufficienti"

            curr_rsi = float(rsi.iloc[-1])
            curr_macd = float(macd_df["MACD_12_26_9"].iloc[-1])
            curr_signal = float(macd_df["MACDs_12_26_9"].iloc[-1])
            macd_cross_bull = curr_macd > curr_signal

            score = 50  # base
            parts = []

            # RSI oversold = molto bullish per un potenziale rimbalzo
            if curr_rsi < 25:
                score += 30
                parts.append(f"RSI estremo oversold ({curr_rsi:.0f})")
            elif curr_rsi < 35:
                score += 20
                parts.append(f"RSI oversold ({curr_rsi:.0f})")
            elif curr_rsi > 75:
                score -= 25
                parts.append(f"RSI overbought ({curr_rsi:.0f})")
            elif curr_rsi > 65:
                score -= 10
                parts.append(f"RSI alto ({curr_rsi:.0f})")

            # MACD bullish cross
            if macd_cross_bull:
                score += 15
                parts.append("MACD bullish cross")
            else:
                score -= 10
                parts.append("MACD bearish")

            # EMA trend direction
            if len(close) >= 50:
                ema20 = float(ta.ema(close, length=20).iloc[-1])
                ema50 = float(ta.ema(close, length=50).iloc[-1])
                if ema20 > ema50:
                    score += 5
                    parts.append("EMA20 > EMA50")
                else:
                    score -= 5

            score = max(0, min(100, score))
            return score, "Momentum: " + ", ".join(parts) if parts else "Momentum neutro"
        except Exception as e:
            return 40, f"Errore momentum: {e}"

    # ── Fattore 4: Volatilità Sweet-Spot ─────────────────────────

    def _score_volatility(self, df: pd.DataFrame) -> tuple[int, str]:
        """
        ATR% del prezzo. Sweet-spot: 2-6% (buona volatilità per profitto).
        < 1% = troppo piatta,  1-2% = ok,  2-6% = ideale,  6-10% = rischioso,  > 10% = pericoloso
        """
        try:
            import pandas_ta as ta
            atr = ta.atr(df["high"], df["low"], df["close"], length=14)
            if atr is None:
                return 40, "ATR non calcolabile"

            price = float(df["close"].iloc[-1])
            atr_pct = float(atr.iloc[-1]) / price * 100

            if 2.0 <= atr_pct <= 6.0:
                return 100, f"ATR% {atr_pct:.2f}% (sweet-spot ideale)"
            elif 1.0 <= atr_pct < 2.0:
                return 65, f"ATR% {atr_pct:.2f}% (volatilità bassa)"
            elif 6.0 < atr_pct <= 10.0:
                return 55, f"ATR% {atr_pct:.2f}% (volatilità alta)"
            elif atr_pct < 1.0:
                return 25, f"ATR% {atr_pct:.2f}% (troppo piatta)"
            else:
                return 20, f"ATR% {atr_pct:.2f}% (pericolosamente volatile)"
        except Exception:
            return 40, "Errore calcolo volatilità"

    # ── Fattore 5: Volume Profile ────────────────────────────────

    def _score_volume_profile(self, df: pd.DataFrame) -> tuple[int, str]:
        """
        Volume crescente (ultime 20 candele vs precedenti 20) indica interesse crescente.
        """
        try:
            if len(df) < 40:
                return 50, "Dati insufficienti per volume profile"

            recent_vol = float(df["volume"].iloc[-20:].mean())
            older_vol = float(df["volume"].iloc[-40:-20].mean())

            if older_vol <= 0:
                return 50, "Volume storico zero"

            ratio = recent_vol / older_vol

            if ratio >= 2.0:
                return 100, f"Volume in esplosione ({ratio:.1f}x)"
            elif ratio >= 1.5:
                return 85, f"Volume in forte crescita ({ratio:.1f}x)"
            elif ratio >= 1.1:
                return 70, f"Volume in crescita ({ratio:.1f}x)"
            elif ratio >= 0.8:
                return 50, f"Volume stabile ({ratio:.1f}x)"
            else:
                return 25, f"Volume in calo ({ratio:.1f}x)"
        except Exception:
            return 40, "Errore volume profile"

    # ── Fattore 6: Price Action ──────────────────────────────────

    def _score_price_action(self, df: pd.DataFrame) -> tuple[int, str]:
        """
        Posizione del prezzo rispetto al range delle ultime 100 candele.
        Vicino al supporto (bottom 25%) = opportunità d'acquisto.
        """
        try:
            window = min(100, len(df))
            recent = df.tail(window)
            high = float(recent["high"].max())
            low = float(recent["low"].min())
            curr = float(df["close"].iloc[-1])

            if high == low:
                return 50, "Range piatto"

            position = (curr - low) / (high - low) * 100  # 0% = supporto, 100% = resistenza

            if position <= 15:
                return 95, f"Prezzo vicino al supporto ({position:.0f}%)"
            elif position <= 30:
                return 80, f"Prezzo nella zona bassa ({position:.0f}%)"
            elif position <= 50:
                return 65, f"Prezzo a metà range ({position:.0f}%)"
            elif position <= 75:
                return 45, f"Prezzo nella zona alta ({position:.0f}%)"
            else:
                return 20, f"Prezzo vicino alla resistenza ({position:.0f}%)"
        except Exception:
            return 40, "Errore price action"
