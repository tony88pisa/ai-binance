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
    def evaluate(self, intel: MarketIntelligence) -> Dict[str, Any]:
        regime = self._detect_regime(intel.macd_1h, intel.rsi_1h)
        consensus = self._calculate_consensus(intel.rsi_5m, intel.rsi_1h, intel.macd_5m, intel.macd_1h)
        atr_stop = intel.atr_5m * 2.0
        
        # Contratto rigoroso: "buy" o "hold"
        decision = "hold"
        confidence = 50
        why_not = "No clear edge detected"
        risk_flags: List[str] = []
        tech_basis: List[str] = [f"RSI 5m: {intel.rsi_5m:.1f}"]
        size_pct = 0.0

        if consensus > 0.65 and intel.rsi_5m < 45 and regime == "TREND_UP":
            decision = "buy"
            confidence = int(consensus * 100)
            size_pct = self._calculate_size(intel.atr_5m, intel.price)
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
                why_not = "Consensus insufficient for entry"

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
            "why_not_trade": why_not
        }

    def _detect_regime(self, macd_1h: float, rsi_1h: float) -> str:
        if macd_1h > 0 and rsi_1h >= 50: return "TREND_UP"
        if macd_1h < 0 and rsi_1h <= 50: return "TREND_DOWN"
        if 40 < rsi_1h < 60: return "RANGE"
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
