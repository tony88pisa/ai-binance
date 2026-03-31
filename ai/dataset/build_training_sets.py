import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from storage.repository import Repository

logger = logging.getLogger("ai.dataset.build_training_sets")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "ai" / "dataset"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

class DatasetBuilder:
    def __init__(self, repo: Repository):
        self.repo = repo

    def generate_alpaca_dataset(self) -> str:
        """Create Alpaca-style JSONL (with 'text' field) for Unsloth from stored decisions and outcomes."""
        with self.repo._get_connection() as conn:
            # Join decisions with outcomes based on ground truth
            # V8.1.1: Use 'status' = 'completed' to only include items with outcomes
            rows = conn.execute(
                """SELECT d.*, o.was_profitable, o.realized_pnl_pct
                   FROM decisions d
                   JOIN trade_outcomes o ON d.id = o.decision_id
                   WHERE d.status = 'completed'"""
            ).fetchall()
            
            dataset = []
            for row in rows:
                instruction = (f"Market Environment: {row['market_regime']} | "
                               f"RSI 5m: {row['rsi_5m']} | MACD 5m: {row['macd_5m']}")
                
                input_data = f"Asset: {row['asset']} | AI Thesis: {row['thesis']}"
                
                if row['was_profitable']:
                    label = f"SUCCESS: Buy action was correct yielding {row['realized_pnl_pct']}%."
                else:
                    label = f"FAILURE: Buy action was incorrect with {row['realized_pnl_pct']}% loss."
                
                # V8.1.1 Requirement: Single 'text' field in Alpaca format for Unsloth
                text_field = (
                    f"### Instruction:\n{instruction}\n\n"
                    f"### Input:\n{input_data}\n\n"
                    f"### Response:\n{label}"
                )
                
                dataset.append({
                    "instruction": instruction,
                    "input": input_data,
                    "output": label,
                    "text": text_field
                })

            if not dataset:
                logger.warning("No completed decision-outcome pairs found for training.")
                return ""

            dataset_id = f"V811_{int(datetime.now(timezone.utc).timestamp())}"
            output_path = DATASET_DIR / f"{dataset_id}.jsonl"
            with open(output_path, "w", encoding="utf-8") as f:
                for entry in dataset:
                    f.write(json.dumps(entry) + "\n")
            
            logger.info(f"Dataset V8.1.1 generated with {len(dataset)} entries at {output_path}")
            return str(output_path)

if __name__ == "__main__":
    from storage.repository import Repository
    db = DatasetBuilder(Repository())
    res = db.generate_alpaca_dataset()
    print(f"Dataset V8.1.1 result: {res}")
