import sqlite3
import os
from pathlib import Path

DB_PATH = Path("H:/ai binance/storage/v8_platform.sqlite")

def check():
    if not DB_PATH.exists():
        print(f"Error: DB not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Check Reviews
    print("--- NVIDIA REVIEWS ---")
    revs = conn.execute("SELECT review_id, created_at, dominant_failures FROM nvidia_reviews ORDER BY created_at DESC").fetchall()
    print(f"Total reviews: {len(revs)}")
    for r in revs:
        print(f"ID: {r['review_id']} | Created: {r['created_at']} | Failures: {r['dominant_failures'][:30]}...")

    # Check Candidates
    print("\n--- CANDIDATE STRATEGIES ---")
    strats = conn.execute("SELECT version_tag, family, created_at FROM strategy_versions WHERE status='candidate' ORDER BY created_at DESC").fetchall()
    print(f"Total candidates: {len(strats)}")
    for s in strats:
        print(f"Tag: {s['version_tag']} | Family: {s['family']} | Created: {s['created_at']}")

    conn.close()

if __name__ == "__main__":
    check()
