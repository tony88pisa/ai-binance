import sqlite3
import os

DB_PATH = 'h:/ai-binance/storage/trade_data.db'

if not os.path.exists(DB_PATH):
    print(f"ERROR: DB not found at {DB_PATH}")
    exit(1)

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check trade_outcomes
    outcomes = cursor.execute('SELECT COUNT(*) FROM trade_outcomes').fetchone()[0]
    total_pnl = cursor.execute('SELECT SUM(realized_pnl_pct) FROM trade_outcomes').fetchone()[0]
    
    # Check decisions
    active = cursor.execute("SELECT COUNT(*) FROM decisions WHERE status IN ('OPEN', 'PENDING')").fetchone()[0]
    
    print(f"Completed Trades: {outcomes}")
    print(f"Total PnL %: {total_pnl if total_pnl else 0.0}")
    print(f"Currently Active: {active}")
    
    conn.close()
except Exception as e:
    print(f"SQLITE ERROR: {e}")
