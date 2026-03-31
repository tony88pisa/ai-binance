import sqlite3
import json
import os
from pathlib import Path

PROJECT_ROOT = Path("H:/ai binance")
V8_DB = PROJECT_ROOT / "storage" / "v8_platform.sqlite"

def verify():
    if not V8_DB.exists():
        print(f"Error: {V8_DB} does not exist.")
        return

    conn = sqlite3.connect(V8_DB)
    conn.row_factory = sqlite3.Row
    
    print("--- 1. Service State (Evolution Loop) ---")
    row = conn.execute("SELECT * FROM service_state WHERE service_name = 'evolution_loop'").fetchone()
    if row:
        print(json.dumps(dict(row), indent=2))
    else:
        print("No evolution_loop state found.")

    print("\n--- 2. Decisions (Completed) ---")
    count = conn.execute("SELECT count(*) FROM decisions WHERE status = 'completed'").fetchone()[0]
    print(f"Total completed decisions: {count}")

    print("\n--- 3. Trade Outcomes ---")
    count = conn.execute("SELECT count(*) FROM trade_outcomes").fetchone()[0]
    print(f"Total trade outcomes: {count}")

    print("\n--- 4. Strategy Versions (Candidates) ---")
    rows = conn.execute("SELECT version_tag, family, created_at, status FROM strategy_versions WHERE status = 'candidate'").fetchall()
    for r in rows:
        print(f"- {r['version_tag']} ({r['family']}) Created: {r['created_at']}")

    conn.close()

if __name__ == "__main__":
    verify()
