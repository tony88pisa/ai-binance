import sqlite3
import json

def research_trades():
    conn = sqlite3.connect('storage/v8_platform.sqlite')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Check open trades
    c.execute('SELECT id, asset, action, timestamp, status FROM decisions WHERE status="OPEN" ORDER BY timestamp ASC')
    rows = [dict(r) for r in c.fetchall()]
    
    print(f"TOTAL_OPEN_TRADES: {len(rows)}")
    print("FIRST_10_OPEN:")
    for r in rows[:10]:
        print(f" {r['id']} | {r['asset']} | {r['timestamp']}")
    
    # Define "Ghost" as older than 24 hours AND no updates (simulated here by timestamp)
    # Since this is a testnet, any trade older than a few hours might be a ghost if the bot is 5m/15m based.
    # Let's count how many are older than 24h.
    # Current time (approx from system): 2026-03-31T12:00:00
    
    print("\n--- API LEARNING DATA ---")
    # Check actual /api/learning data
    c.execute("SELECT COUNT(*) FROM trade_outcomes")
    outcome_cnt = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM trade_outcomes WHERE was_profitable=1")
    win_cnt = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(realized_pnl_pct),0) FROM trade_outcomes")
    total_pnl = c.fetchone()[0]
    
    print(f"Outcomes: {outcome_cnt}")
    print(f"Wins: {win_cnt}")
    print(f"Total PnL %: {total_pnl * 100:.2f}")

    conn.close()

if __name__ == '__main__':
    research_trades()
