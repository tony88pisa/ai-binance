import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("H:/ai binance")
sys.path.insert(0, str(PROJECT_ROOT))

from ai.dataset.build_training_sets import DatasetBuilder
from storage.repository import Repository

def run_fase_d():
    print(f"--- FASE D: COERENZA DATASET / TRAINER ---")
    repo = Repository()
    
    # 1. Clean old datasets for clear proof
    dataset_dir = PROJECT_ROOT / "ai" / "dataset"
    for f in dataset_dir.glob("V811_*.jsonl"):
        f.unlink()

    # 2. Inject dummy completed data for generation
    # Since DB is clean, we need at least one completed decision+outcome
    with repo._get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO bot_sessions (id, bot_name, env, started_at) VALUES ('D-SESS', 'BuilderTest', 'testlab', '2026-03-29')")
        conn.execute("""
            INSERT OR IGNORE INTO decisions (id, timestamp_utc, bot_session_id, asset, action, confidence, thesis, status, market_regime, rsi_5m, macd_5m) 
            VALUES ('D-DEC-001', '2026-03-29T19:00:00', 'D-SESS', 'BTC/USDC', 'buy', 92, 'Bullish Divergence', 'completed', 'bullish', 32.5, 0.002)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO trade_outcomes (id, decision_id, asset, open_at, closed_at, realized_pnl_pct, realized_pnl_abs, was_profitable) 
            VALUES ('D-OUT-001', 'D-DEC-001', 'BTC/USDC', '19:00', '19:30', 3.4, 15.0, 1)
        """)
        conn.commit()

    # 3. Generate
    builder = DatasetBuilder(repo)
    ds_path = builder.generate_alpaca_dataset()
    
    if ds_path and os.path.exists(ds_path):
        print(f"PASS: Dataset generated at {ds_path}")
        
        # 4. Prove Format
        with open(ds_path, "r", encoding="utf-8") as f:
            first_rows = [json.loads(f.readline()) for _ in range(1)]
            row = first_rows[0]
            print(f"  > Dataset Sample (First Row):")
            print(f"    Instruction: {row.get('instruction')}")
            print(f"    Input: {row.get('input')}")
            print(f"    Output: {row.get('output')}")
            print(f"    TEXT FIELD (V8.1.1): {row.get('text')[:100]}...")
            
            if "text" in row and "### Instruction:" in row["text"]:
                print(f"  > PASS: 'text' field format is correct Alpaca.")
            else:
                print(f"  > FAIL: 'text' field is MISSING or INCORRECT.")
    else:
        print(f"FAIL: Dataset generation failed.")

    # 5. Trainer Dry Import
    try:
        from ai.training.unsloth_trainer import run_training_v811
        print(f"PASS: unsloth_trainer.py Import check (Ready for training loop)")
    except Exception as e:
        print(f"FAIL: unsloth_trainer.py Import check: {e}")

if __name__ == "__main__":
    run_fase_d()
