import sqlite3
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("H:/ai binance")
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "storage" / "v8_platform.sqlite"

def verify_db():
    print(f"--- DATABASE COHERENCE CHECK (V8.1.1) ---")
    
    if not DB_PATH.exists():
        print(f"ERROR: Database file not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check Tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = [
        "bot_sessions", "model_versions", "strategy_versions", 
        "live_deployments", "strategy_patterns", "learned_changes", 
        "decisions", "trade_outcomes", "service_state", 
        "training_runs", "validation_runs"
    ]
    
    print(f"Found {len(tables)} tables.")
    missing = [t for t in required_tables if t not in tables]
    
    if missing:
        print(f"MISSING TABLES: {missing}")
    else:
        print(f"CHECK: All required tables exist. (OK)")
        
    # 2. Check 'status' column in 'decisions'
    cursor.execute("PRAGMA table_info(decisions);")
    columns = [row[1] for row in cursor.fetchall()]
    if "status" in columns:
        print(f"CHECK: Column 'status' exists in 'decisions' table. (OK)")
    else:
        print(f"ERROR: Column 'status' MISSING in 'decisions' table.")
        
    # 3. Test Query (Real logic from build_training_sets.py)
    try:
        cursor.execute("""
            SELECT d.*, o.was_profitable 
            FROM decisions d 
            JOIN trade_outcomes o ON d.id = o.decision_id 
            WHERE d.status = 'completed'
        """)
        print(f"CHECK: SQL Join query (Decisions + Outcomes) executed successfully. (OK)")
    except Exception as e:
        print(f"ERROR: SQL query failed: {e}")
        
    conn.close()

if __name__ == "__main__":
    verify_db()
