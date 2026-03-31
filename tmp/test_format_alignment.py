import sys
import unittest
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path("H:/ai binance")
sys.path.insert(0, str(PROJECT_ROOT))

from ai.dataset.build_training_sets import DatasetBuilder
from storage.repository import Repository

def verify_alignment():
    print(f"--- FORMAT ALIGNMENT CHECK (V8.1.1) ---")
    
    # 1. Dataset Builder Field Generation
    repo = Repository()
    db = DatasetBuilder(repo)
    
    # Mock some data to test generation
    with repo._get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO bot_sessions (id, bot_name, env, started_at) VALUES ('TEST-SESS', 'TestBot', 'testlab', '2026-03-29T18:00:00')")
        conn.execute("""
            INSERT OR IGNORE INTO decisions (id, timestamp_utc, asset, action, confidence, thesis, status) 
            VALUES ('TEST-DEC', '2026-03-29T18:30:00', 'BTC/USDC', 'buy', 85, 'Moon', 'completed')
        """)
        conn.execute("""
            INSERT OR IGNORE INTO trade_outcomes (id, decision_id, asset, open_at, closed_at, realized_pnl_pct, realized_pnl_abs, was_profitable) 
            VALUES ('TEST-OUT', 'TEST-DEC', 'BTC/USDC', '18:30', '19:00', 2.5, 12.0, 1)
        """)
        conn.commit()

    ds_path = db.generate_alpaca_dataset()
    if ds_path and Path(ds_path).exists():
        with open(ds_path, "r", encoding="utf-8") as f:
            first_line = json.loads(f.readline())
            if "text" in first_line:
                print(f"CHECK: Dataset JSONL contains 'text' field. (OK)")
                if "### Instruction:" in first_line["text"]:
                    print(f"CHECK: 'text' field format is Alpaca (### Instruction:). (OK)")
            else:
                print(f"ERROR: Dataset JSONL MISSING 'text' field.")
    else:
        print(f"ERROR: Dataset generation failed (No data or query error).")

    # 2. Unsloth Trainer Field Check
    with open(PROJECT_ROOT / "ai" / "training" / "unsloth_trainer.py", "r", encoding="utf-8") as f:
        content = f.read()
        if 'dataset_text_field = "text"' in content:
            print(f"CHECK: Unsloth Trainer synchronized on 'dataset_text_field = \"text\"'. (OK)")
        else:
            print(f"ERROR: Unsloth Trainer MISMATCH (dataset_text_field is NOT \"text\").")

if __name__ == "__main__":
    verify_alignment()
