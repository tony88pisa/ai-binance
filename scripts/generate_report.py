"""
Post-Trade Review & Evaluation Report Generator.
Run: python scripts/generate_report.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.manager import MemoryManager
from config.settings import get_settings

def print_separator(char="=", length=60):
    print(char * length)

def main():
    settings = get_settings()
    mgr = MemoryManager()
    
    print("\n")
    print_separator("=", 60)
    print(f"   V6.0 BOT VALIDATION REPORT: [{settings.model.validation_mode.upper()}] MODE")
    print_separator("=", 60)

    try:
        ev = mgr.compute_evaluation()
    except Exception as e:
        print(f"Error computing evaluation: {e}")
        sys.exit(1)
        
    print(f"\n[GLOBAL METRICS]")
    print(f"Total Decisions Made:     {ev.total_decisions}")
    print(f"Total Trades Executed:    {ev.total_executed}")
    print(f"Risk Gate Block Rate:     {((ev.total_decisions - ev.total_executed) / max(1, ev.total_decisions)) * 100:.1f}%")
    print(f"Win Rate:                 {ev.win_rate * 100:.1f}% ({ev.total_profitable}W / {ev.total_losing}L)")
    print(f"Realized Average PnL:     {ev.avg_pnl_pct:+.2f}%")
    print(f"Average Hold Time:        {ev.avg_hold_minutes:.1f} m")
    
    print(f"\n[CONFIDENCE CALIBRATION]")
    print(f"Avg Confidence (Winners): {ev.avg_confidence_winners:.1f}%")
    print(f"Avg Confidence (Losers):  {ev.avg_confidence_losers:.1f}%")
    print(f"Calibration State:        {ev.confidence_calibration.upper()}")
    
    print(f"\n[ASSET BREAKDOWN]")
    for asset, data in ev.per_asset.items():
        wrate = data.get("win_rate", 0) * 100
        pnl = data.get("avg_pnl", 0)
        print(f"  - {asset.ljust(10)} | Trades: {data.get('trades', 0):<3} | WinRate: {wrate:>5.1f}% | AvgPnL: {pnl:+.2f}%")

    print(f"\n[REGIME BREAKDOWN]")
    for regime, data in ev.per_regime.items():
        wrate = data.get("win_rate", 0) * 100
        pnl = data.get("avg_pnl", 0)
        print(f"  - {regime.ljust(15)} | Trades: {data.get('trades', 0):<3} | WinRate: {wrate:>5.1f}% | AvgPnL: {pnl:+.2f}%")
        
    print_separator("-", 60)
    print("\n* All metrics derived strictly from OutcomeRecords linked to generated DecisionRecords.")
    print("* Validated offline via local inference/mock/cache. Not financial advice.\n")

if __name__ == "__main__":
    main()
