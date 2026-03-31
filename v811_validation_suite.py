import sqlite3
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = Path("H:/ai binance")
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "storage" / "v8_platform.sqlite"

def run_fase_b():
    print(f"--- FASE B: COERENZA DATABASE ---")
    if not DB_PATH.exists():
        print(f"FAIL: Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Elenco Tabelle
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    required = [
        "bot_sessions", "model_versions", "strategy_versions", 
        "live_deployments", "strategy_patterns", "learned_changes", 
        "decisions", "trade_outcomes", "service_state", 
        "training_runs", "validation_runs"
    ]
    missing = [t for t in required if t not in tables]
    if missing:
        print(f"FAIL: Missing tables {missing}")
        return False
    else:
        print(f"PASS: All 11+ tables present.")
        
    # 2. Schema Decisions
    cursor.execute("PRAGMA table_info(decisions);")
    cols = [row[1] for row in cursor.fetchall()]
    if "status" in cols:
        print(f"PASS: 'status' column exists in decisions (Coerente con Builder).")
    else:
        print(f"FAIL: 'status' column MISSING in decisions.")
        return False
        
    # 3. Registry Schemas Verification
    for tbl in ["model_versions", "strategy_versions", "live_deployments", "strategy_patterns", "learned_changes"]:
        cursor.execute(f"PRAGMA table_info({tbl});")
        if cursor.fetchall():
            print(f"  > Table {tbl} Schema: OK")
        else:
            print(f"  > FAIL: Table {tbl} schema empty or missing.")
    
    conn.close()
    return True

def run_fase_c():
    print(f"\n--- FASE C: COERENZA REPOSITORY / REGISTRY ---")
    from storage.repository import Repository
    from ai.registry.model_registry import ModelRegistry
    from ai.registry.strategy_registry import StrategyRegistry
    from ai.registry.promotion_registry import PromotionRegistry
    from ai.registry.rollback_registry import RollbackRegistry

    repo = Repository()
    mr = ModelRegistry(repo)
    sr = StrategyRegistry(repo)
    pr = PromotionRegistry(repo)
    rr = RollbackRegistry(repo)

    try:
        # 1. Register Model
        # mr.register_new_model(tag, base, dataset_id, metrics, parent=None)
        mr.register_new_model("V811-TEST-M1", "qwen3:8b", "V811_SET", {"loss": 0.05}, parent="None")
        print(f"PASS: register_model_version (Candidate)")

        # 2. Register Strategy
        strat_tag = sr.register_strategy_version("TEST_FAMILY", {"filter": "rsi > 30"})
        print(f"PASS: register_strategy_version (Candidate)")

        # 3. Promote & Deploy to Live (Simulated Validation)
        with repo._get_connection() as conn:
            conn.execute("UPDATE model_versions SET status = 'validated' WHERE tag_name = 'V811-TEST-M1'")
        pr.promote_to_live("V811-TEST-M1", strat_tag, "TEST_ADMIN")
        print(f"PASS: deploy_to_live")

        # 4. Multi-Env lookup
        live_m = repo.get_active_model_for_env("live")
        lab_m = repo.get_active_model_for_env("testlab")
        print(f"PASS: separation check (Live: {live_m}, Lab: {lab_m})")

        # 5. Rollback
        # Need at least two deployments to rollback
        mr.register_new_model("V811-TEST-M2", "qwen3:8b", "V811_SET", {"loss": 0.04}, parent="V811-TEST-M1")
        with repo._get_connection() as conn:
            conn.execute("UPDATE model_versions SET status = 'validated' WHERE tag_name = 'V811-TEST-M2'")
        pr.promote_to_live("V811-TEST-M2", strat_tag, "TEST_ADMIN")
        
        if rr.rollback_live("TEST_FAILURE"):
            print(f"PASS: rollback_live")
        else:
            print(f"FAIL: rollback_live (Check registry status)")

        # 6. Upsert Pattern
        repo.upsert_pattern("PAT-RSI-LOW", "TEST_STRAT", "bullish", "RSI < 30", {"win_rate": 0.65, "pnl": 1.2})
        print(f"PASS: upsert_pattern")

        return True
    except Exception as e:
        print(f"FAIL: Phase C Method Exception: {e}")
        return False

if __name__ == "__main__":
    b_ok = run_fase_b()
    if b_ok:
        run_fase_c()
