import sqlite3
import json

def report_schema():
    db_file = 'storage/v8_platform.sqlite'
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    
    print(f"REAL DB FILE: {db_file}")
    
    # A. sqlite_master
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print("\n[TABLES FOUND]")
    for t in tables:
        print(f"- {t['name']}")
        
    # B. table_info
    relevant = ['decisions', 'trade_outcomes', 'service_state', 'strategy_versions']
    for table in relevant:
        print(f"\n--- PRAGMA table_info({table}) ---")
        try:
            info = conn.execute(f"PRAGMA table_info({table});").fetchall()
            for col in info:
                print(dict(col))
        except Exception as e:
            print(f"Error reading {table}: {e}")

    # C. Real Row Evidence
    print("\n[REAL ROW EVIDENCE]")
    for table in ['service_state', 'trade_outcomes', 'strategy_versions']:
        print(f"\n--- First row of {table} ---")
        try:
            row = conn.execute(f"SELECT * FROM {table} LIMIT 1;").fetchone()
            if row:
                print(dict(row))
            else:
                print("No rows found.")
        except Exception as e:
            print(f"Error reading row from {table}: {e}")
            
    conn.close()

if __name__ == "__main__":
    report_schema()
