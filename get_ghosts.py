import sqlite3
import json

def get_ghost_trades():
    conn = sqlite3.connect('storage/v8_platform.sqlite')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # All open trades
    c.execute('SELECT id, asset, action, timestamp, status FROM decisions WHERE status="OPEN" ORDER BY timestamp ASC')
    rows = [dict(r) for r in c.fetchall()]
    
    # SQL proposed for deletion
    # Since these are all ETH/USDT duplicates from today 09:17 to 09:22
    # We can use a time-based or ID based filter.
    
    report = {
        "count": len(rows),
        "trades": rows,
        "sql_proposal": "DELETE FROM decisions WHERE status='OPEN' AND timestamp < datetime('now', '-30 minutes')"
    }
    
    with open("ghost_trades_report.json", "w") as f:
        json.dump(report, f, indent=2)
    conn.close()

if __name__ == '__main__':
    get_ghost_trades()
