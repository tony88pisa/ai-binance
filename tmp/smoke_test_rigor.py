import sqlite3
import json

def smoke_test():
    db_file = 'storage/v8_platform.sqlite'
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    
    print("--- 1. sqlite_master (TABLES) ---")
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print([t['name'] for t in tables])
    
    for table in ['decisions', 'trade_outcomes', 'service_state']:
        print(f"\n--- 2. PRAGMA table_info({table}) ---")
        info = [dict(col) for col in conn.execute(f"PRAGMA table_info({table});").fetchall()]
        print(json.dumps(info, indent=2))
        
    conn.close()

if __name__ == "__main__":
    smoke_test()
