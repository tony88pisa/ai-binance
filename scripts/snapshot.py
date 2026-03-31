"""
V6.0 Daily Snapshot Engine.
Run: python scripts/snapshot.py

Collects evaluation metrics and system health flags, then appends to daily_snapshot.csv.
"""
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.manager import MemoryManager
from config.settings import get_settings

snapshot_file = Path("user_data/logs/daily_snapshot.csv")

def get_alert_counts():
    """Scan alerts.log for timeouts and stale events today."""
    timeouts = 0
    stale = 0
    log_file = Path("user_data/logs/alerts.log")
    if log_file.exists():
        today_str = datetime.now().strftime("%Y-%m-%d")
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if today_str in line:
                    if "Timeout" in line or "Unreachable" in line or "Unresponsive" in line:
                        timeouts += 1
                    if "Stale" in line:
                        stale += 1
    return timeouts, stale

def main():
    settings = get_settings()
    mgr = MemoryManager()
    
    # 1. Gather Metrics
    try:
        ev = mgr.compute_evaluation()
    except Exception:
        print("Failed to compute memory evaluation.")
        sys.exit(1)
        
    timeouts, stale_events = get_alert_counts()
    
    # 2. Count actual open trades from sqlite
    open_trades = 0
    try:
        from freqtrade.persistence import Trade, init_db
        init_db('sqlite:///tradesv3.dryrun.sqlite')
        open_trades = Trade.session.query(Trade).filter(Trade.is_open == True).count()
    except Exception:
        pass
        
    # 3. Model avg latency (simplification: if we have tracking, or just N/A for now)
    # Since decision records don't track latency currently, we'll mark it N/A if missing
    # but we can do a live ping test right now to get current latency.
    current_latency = 0
    try:
        import requests
        start_t = time.time()
        requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": settings.model.model_name, "prompt": "a", "stream": False, "keep_alive": "5m"},
            timeout=10
        )
        current_latency = int((time.time() - start_t) * 1000)
    except Exception:
        current_latency = -1

    # 4. Write CSV
    write_header = not snapshot_file.exists()
    snapshot_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(snapshot_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "date_time", "operational_state", "current_latency_ms", 
                "stale_events_today", "timeouts_today", "risk_vetoes", 
                "total_decisions", "executed_trades", "open_trades", "realized_pnl_pct"
            ])
            
        vetoes = ev.total_decisions - ev.total_executed
        
        v_mode = settings.model.validation_mode.lower()
        if v_mode == "mock":
            op_state = "mock_validation"
        elif v_mode == "cached":
            op_state = "cached_validation"
        else:
            op_state = "operational_real"

        writer.writerow([
            datetime.now().isoformat(timespec='minutes'),
            op_state,
            current_latency,
            stale_events,
            timeouts,
            vetoes,
            ev.total_decisions,
            ev.total_executed,
            open_trades,
            f"{ev.avg_pnl_pct:.2f}"
        ])
    
    if op_state != "operational_real":
        print(f"[Warning] UNOFFICIAL SNAPSHOT: Operational state is '{op_state}'. This does NOT count toward Live Gates.")
    else:
        print(f"OFFICIAL PAPER-TRADING SNAPSHOT LOGGED to {snapshot_file}")
        
    print(f"Decisions: {ev.total_decisions} | Executed: {ev.total_executed} | Vetoes: {vetoes} | PnL: {ev.avg_pnl_pct:.2f}%")

if __name__ == "__main__":
    main()
