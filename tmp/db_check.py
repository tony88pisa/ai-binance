import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path("storage/v8_platform.sqlite")

def check_db():
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    print("--- TABLES ---")
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur]
    print(tables)
    
    if "nvidia_reviews" in tables:
        print("\n--- SCHEMA: nvidia_reviews ---")
        cur = conn.execute("PRAGMA table_info(nvidia_reviews)")
        print([dict(r) for r in cur])
        
        print("\n--- LATEST REVIEW ---")
        cur = conn.execute("SELECT * FROM nvidia_reviews ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        if row: print(dict(row))
        else: print("No reviews found.")
    else:
        print("\nWARNING: Table nvidia_reviews MISSING.")
        
    print("\n--- SERVICE_STATE ---")
    cur = conn.execute("SELECT * FROM service_state")
    print([dict(r) for r in cur])
    
    conn.close()

if __name__ == "__main__":
    check_db()
