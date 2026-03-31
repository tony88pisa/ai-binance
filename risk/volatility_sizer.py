"""
VOLATILITY SIZER V8.3
Adaptive position sizing based on ATR (Average True Range).
"""
import logging
from typing import Dict, Tuple

logger = logging.getLogger("risk.volatility_sizer")

class VolatilitySizer:
    def __init__(self, base_stake: float = 10.0, target_risk_pct: float = 0.01):
        self.base_stake = base_stake
        self.target_risk_pct = target_risk_pct

    def calculate_stake(self, current_balance: float, atr: float, price: float) -> float:
        """
        Calculate stake using the 'Risk Parity' approach.
        Position Size = (Balance * Risk%) / ATR.
        We cap the result at base_stake for safety in V8.3 testing.
        """
        if atr <= 0:
            return self.base_stake

        # Calculate how much balance to risk (e.g. 1% of 1000 = 10)
        risk_amount = current_balance * self.target_risk_pct
        
        # Position size in units = risk_amount / atr
        # Position size in currency = units * price
        units = risk_amount / atr
        dynamic_stake = units * price
        
        # Sizing Multiplier (Phase 1 influence)
        # If ATR is 2% of price, it's normal. If ATR is 5% of price, it's high volatility.
        volatility_norm = atr / price
        
        if volatility_norm > 0.05: # High Volatility (>5%)
            logger.info(f"High volatility detected ({volatility_norm:.2%}). Reducing stake.")
            dynamic_stake *= 0.5
        elif volatility_norm < 0.01: # Low Volatility (<1%)
            logger.info(f"Low volatility detected ({volatility_norm:.2%}). Increasing stake confidence.")
            dynamic_stake *= 1.2

        # Final Cap for TestLab/DryRun
        final_stake = min(dynamic_stake, self.base_stake * 1.5)
        
        logger.info(f"Volatility Sizer: ATR={atr:.2f}, Price={price:.2f}, DynamicStake={dynamic_stake:.2f} -> Final={final_stake:.2f}")
        return round(final_stake, 2)

    @staticmethod
    def get_adaptive_stops(regime: str, volatility_norm: float) -> Tuple[float, float]:
        """
        Return (stop_loss_pct, take_profit_pct) based on market regime.
        - TREND: Wider stops to catch movement.
        - RANGE: Tighter stops for quick exits.
        """
        # Baseline
        sl = -0.05
        tp = 0.10

        from ai.regime_detector import MarketRegime

        if regime in [MarketRegime.TREND_UP, MarketRegime.BULL]:
            # Let it run
            sl = -0.06 if volatility_norm > 0.03 else -0.04
            tp = 0.15
        elif regime in [MarketRegime.RANGING, MarketRegime.SIDEWAYS]:
            # Tight and fast
            sl = -0.03
            tp = 0.05
        elif regime == MarketRegime.CRASH:
            # Extreme caution
            sl = -0.02
            tp = 0.03
            
        return sl, tp
