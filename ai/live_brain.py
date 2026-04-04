from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class MarketIntelligence:
    asset: str
    price: float
    rsi_5m: float
    rsi_1h: float
    macd_5m: float
    macd_1h: float
    atr_5m: float

class LiveBrain:
    def evaluate(self, intel: Any) -> Dict[str, Any]:
        """Evaluates market signals. Supports both dictionary and MarketIntelligence object."""
        # Duck-typing or conversion to dict if it's a dataclass
        if hasattr(intel, "__dataclass_fields__"):
            data = {field: getattr(intel, field) for field in intel.__dataclass_fields__}
        elif isinstance(intel, dict):
            data = intel
        else:
            raise TypeError(f"LiveBrain.evaluate expects dict or MarketIntelligence, got {type(intel)}")

        def get_val(key, default=0.0):
            return data.get(key, default)

        m1h = get_val("macd_1h")
        r1h = get_val("rsi_1h", 50.0)
        r5m = get_val("rsi_5m", 50.0)
        m5m = get_val("macd_5m")
        a5m = get_val("atr_5m")
        price = get_val("price")

        regime = self._detect_regime(m1h, r1h)
        consensus = self._calculate_consensus(r5m, r1h, m5m, m1h)
        atr_stop = a5m * 2.0
        
        # Contratto rigoroso: "buy" o "hold"
        decision = "hold"
        confidence = 50
        why_not = "No clear edge detected"
        risk_flags: List[str] = []
        tech_basis: List[str] = [f"RSI 5m: {r5m:.1f}"]
        size_pct = 0.0

        if consensus > 0.65 and r5m < 45 and regime == "TREND_UP":
            decision = "buy"
            confidence = int(consensus * 100)
            size_pct = self._calculate_size(a5m, price)
            why_not = ""
            tech_basis.append("Oversold dip in confirmed Uptrend")
        else:
            decision = "hold"
            if regime == "HIGH_VOL_CHAOS":
                risk_flags.append("Chaos regime blocking setups")
            elif regime == "TREND_DOWN":
                why_not = "Declined: asset is in downtrend, spot bot holds"
                confidence = int((1.0 - consensus) * 100)
            else:
                rsi_val = float(data.get("rsi_5m") if data.get("rsi_5m") is not None else 50.0)
                regime_val = data.get("regime") or "momentum"
                why_not = f"Exploratory analysis on {data.get('asset', 'unknown')}: Optimize RSI entry threshold ({rsi_val:.1f}) for {regime_val}"
        
        return {
            "decision": decision,
            "confidence": confidence,
            "regime": regime,
            "consensus_score": round(consensus, 2),
            "position_size_pct": round(size_pct, 4),
            "atr_stop_distance": round(atr_stop, 4),
            "thesis": f"System determined {decision} (Conf: {confidence}%) based on {regime}.",
            "technical_basis": tech_basis,
            "risk_flags": risk_flags,
            "why_not_trade": why_not,
            # Return inputs for consumer modules (daemon/dashboard)
            "rsi_5m": r5m,
            "rsi_1h": r1h,
            "macd_5m": m5m,
            "macd_1h": m1h,
            "atr_5m": a5m,
            "price": price
        }

    def _detect_regime(self, macd_1h: float, rsi_1h: float) -> str:
        if (macd_1h or 0) > 0 and (rsi_1h or 50) >= 50: return "TREND_UP"
        if (macd_1h or 0) < 0 and (rsi_1h or 50) <= 50: return "TREND_DOWN"
        if 40 < (rsi_1h or 50) < 60: return "RANGE"
        return "HIGH_VOL_CHAOS"

    def _calculate_consensus(self, rsi5: float, rsi1h: float, macd5: float, macd1h: float) -> float:
        score = 0.5
        if rsi5 < 40: score += 0.15
        if rsi1h < 45: score += 0.10
        if rsi5 > 60: score -= 0.15
        if rsi1h > 55: score -= 0.10
        if macd5 > 0: score += 0.10
        if macd1h > 0: score += 0.15
        if macd5 < 0: score -= 0.10
        if macd1h < 0: score -= 0.15
        return max(0.0, min(1.0, score))

    def _calculate_size(self, atr: float, price: float) -> float:
        if price <= 0 or atr <= 0: return 0.0
        # Profilo prudente: rischio 1% per trade. 
        risk_per_trade = 0.01 
        stop_pct = (atr * 2.0) / price
        if stop_pct <= 0: return 0.0
        size = risk_per_trade / stop_pct
        return min(0.33, size) # max 33% del capitale
