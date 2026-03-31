import sqlite3
import json
import os

def smoke_v82():
    db_path = 'storage/v8_platform.sqlite'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("--- 1. trade_outcomes info ---")
    cols = [dict(r) for r in conn.execute('PRAGMA table_info(trade_outcomes);').fetchall()]
    print(json.dumps(cols, indent=2))
    
    print("\n--- 2. nvidia_reviews check ---")
    tbl = [dict(r) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nvidia_reviews';").fetchall()]
    print(json.dumps(tbl, indent=2))
    
    conn.close()
    
    print("\n--- 3. Budget Check ---")
    os.environ['NVIDIA_API_KEY'] = 'FAKE_KEY'
    os.environ['NVIDIA_MAX_ESTIMATED_INPUT_TOKENS'] = '5'
    from ai.nvidia_client import NvidiaClient
    client = NvidiaClient()
    res = client.review_closed_trades([{'test':'data_too_large'}])
    print(f"Budget Blocked Test Result: {res}")

if __name__ == "__main__":
    smoke_v82()
