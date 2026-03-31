"""
VERIFY MODULE 11 — PHASE 2
Test script for Dynamic Risk Management logic.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from risk.gate import evaluate_proposal
from risk.volatility_sizer import VolatilitySizer
from ai.types import TradeProposal, Action, RiskVerdict

def test_risk_gate_daily_limit():
    print("Testing Daily Loss Limit (-3%)...")
    proposal = TradeProposal(asset="BTC/USDC", action=Action.BUY, confidence=85, reason="Test")
    
    # Case: -4% Daily PnL
    res = evaluate_proposal(proposal, current_wallet_balance=1000, open_trades_count=0, daily_pnl_pct=-0.04)
    assert res.verdict == RiskVerdict.BLOCKED
    assert "daily_loss_limit_active" in res.risk_flags
    print("✓ Daily Limit Blocked at -4%")

def test_volatility_sizing():
    print("\nTesting Volatility Sizing (ATR)...")
    base_stake = 100.0
    sizer = VolatilitySizer(base_stake=base_stake)
    
    # Case 1: Low Vol (ATR $100 on $50,000 price = 0.2%)
    # Risk 1% of 200 = 2. Units = 2/100 = 0.02. Stake = 0.02 * 50000 = 1000 (Capped at 150)
    # Wait, let's use balance=500. Risk=5. Units=5/100=0.05. Stake=0.05*50000=2500 (Still capped)
    
    # Case 1: Balance=100. Risk=1. Units=1/5000=0.0002. Stake=10.
    stake_low = sizer.calculate_stake(100, 100, 50000) # ATR 0.2%
    print(f"Low Vol Stake: {stake_low}")
    
    # Case 2: High Vol (ATR 2501 on $50,000 price = 5.002%) -> Slashes stake by 50%
    stake_high = sizer.calculate_stake(100, 2600, 50000) # ATR 5.2%
    print(f"High Vol Stake: {stake_high}")
    
    assert stake_high < stake_low
    print("✓ High volatility correctly reduces stake")

def test_adaptive_stops():
    print("\nTesting Adaptive Stops by Regime...")
    # BULL Regime
    sl_bull, tp_bull = VolatilitySizer.get_adaptive_stops("TREND_UP", 0.02)
    print(f"BULL: SL={sl_bull}, TP={tp_bull}")
    
    # CRASH Regime
    sl_crash, tp_crash = VolatilitySizer.get_adaptive_stops("CRASH", 0.08)
    print(f"CRASH: SL={sl_crash}, TP={tp_crash}")
    
    assert sl_crash > sl_bull # -0.02 > -0.06 (means tighter)
    assert tp_crash < tp_bull
    print("✓ Adaptive stops correctly adjusted for risk")

if __name__ == "__main__":
    try:
        test_risk_gate_daily_limit()
        test_volatility_sizing()
        test_adaptive_stops()
        print("\nALL PHASE 2 TESTS PASSED! 🚀")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
