"""
Risk Gate — Independent risk validation layer.

This module evaluates TradeProposals against hard risk limits.
It sits between the AI Decision Engine and the trade execution logic,
ensuring the AI cannot blow up the account even if it hallucinates.

Responsibilities:
- Enforce stake caps (relative and absolute)
- Enforce circuit breakers (daily loss, consecutive losses)
- Block risky trades in extreme fear regimes
- Block low data quality trades unless confidence is extremely high
"""
from __future__ import annotations

import logging

from ai.types import (
    Action, RiskAssessment, RiskVerdict, TradeProposal
)
from config.settings import get_settings
from risk.volatility_sizer import VolatilitySizer

logger = logging.getLogger("risk.gate")


def evaluate_proposal(
    proposal: TradeProposal,
    current_wallet_balance: float,
    open_trades_count: int,
    consecutive_losses: int = 0,
    daily_pnl_pct: float = 0.0,
) -> RiskAssessment:
    """Evaluate a TradeProposal and return a RiskAssessment."""
    settings = get_settings()
    flags = []
    
    # 1. Base validation
    if proposal.action != Action.BUY:
        # We only risk-gate BUY decisions. HOLD/SELL are inherently safe.
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.APPROVED,
            approved_stake=0.0,
            reason="Not a BUY action"
        )
        
    # 2. Extract intelligence context
    intel = proposal.intelligence_snapshot or {}
    decision_ctx = proposal.decision or {}
    
    data_quality = decision_ctx.get("data_quality", "low")
    macro_risk = intel.get("macro_risk_level", 0.5)
    confidence = proposal.confidence
    
    # 3. Hard Blocks (Circuit Breakers)
    if daily_pnl_pct <= -0.03:
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.BLOCKED,
            approved_stake=0.0,
            reason=f"Daily loss limit reached ({daily_pnl_pct:.2%})",
            risk_flags=["daily_loss_limit_active"]
        )

    if consecutive_losses >= settings.risk.max_consecutive_losses:
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.BLOCKED,
            approved_stake=0.0,
            reason=f"Circuit breaker: {consecutive_losses} consecutive losses",
            risk_flags=["circuit_breaker_active"]
        )
        
    if open_trades_count >= settings.risk.max_open_trades:
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.BLOCKED,
            approved_stake=0.0,
            reason="Max open trades reached",
            risk_flags=["max_trades_reached"]
        )

    # 4. Data Quality & Macro Risk Blocks
    if data_quality == "low" and confidence < 80:
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.BLOCKED,
            approved_stake=0.0,
            reason=f"Low data quality requires min 80% confidence (got {confidence}%)",
            risk_flags=["low_data_quality_block"]
        )
        
    if macro_risk > 0.8 and confidence < 75:
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.BLOCKED,
            approved_stake=0.0,
            reason=f"Extreme macro risk requires min 75% confidence (got {confidence}%)",
            risk_flags=["extreme_macro_risk_block"]
        )

    # 5. Stake Sizing (Position Management)
    # Get Market Context for Sizing
    regime = intel.get("market_regime", "UNKNOWN")
    atr = intel.get("atr", 0.0)
    price = intel.get("close_price", 0.0)

    # Calculate Max Allowed Stake (Baseline)
    abs_cap = settings.risk.max_stake_abs
    rel_cap = current_wallet_balance * settings.risk.max_stake_pct
    max_allowed = min(abs_cap, rel_cap) if abs_cap > 0 else rel_cap
    
    # 5a. Apply Volatility Sizer (Phase 2)
    sizer = VolatilitySizer(base_stake=max_allowed)
    vol_stake = sizer.calculate_stake(current_wallet_balance, atr, price)
    
    # 5b. Apply Risk Penalties
    penalty = 0.0
    
    # Penalty: Consecutive losses
    if consecutive_losses > 0:
        penalty += (consecutive_losses * 0.15)  # -15% per loss
        flags.append(f"consecutive_loss_penalty_{consecutive_losses}")
        
    # Penalty: Medium data quality
    if data_quality == "medium" and confidence < 80:
        penalty += 0.25
        flags.append("medium_quality_penalty")
        
    # Penalty: High macro risk
    if macro_risk > 0.6:
        penalty += 0.20
        flags.append("macro_risk_penalty")

    # Apply penalty (max 75% reduction)
    penalty = min(0.75, penalty)
    approved_stake = vol_stake * (1 - penalty)
    
    # Minimum stake enforcement
    if approved_stake < 2.0:
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.BLOCKED,
            approved_stake=0.0,
            reason="Approved stake falls below minimum threshold after risk penalties",
            risk_flags=flags + ["stake_too_small"]
        )

    # 6. Final Verdict
    if approved_stake < vol_stake:
        return RiskAssessment(
            proposal=proposal,
            verdict=RiskVerdict.REDUCED,
            approved_stake=round(approved_stake, 2),
            reason=f"Stake reduced by {penalty*100:.0f}% due to risk factors",
            risk_flags=flags
        )
        
    return RiskAssessment(
        proposal=proposal,
        verdict=RiskVerdict.APPROVED,
        approved_stake=round(approved_stake, 2),
        reason="Clean risk profile",
        risk_flags=flags
    )
