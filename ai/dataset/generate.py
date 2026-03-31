import sqlite3
import json
from pathlib import Path

import os
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "tradesv3.dryrun.sqlite"
MEMORY_PATH = PROJECT_ROOT / "user_data" / "memory_v2.json"
OUTPUT_PATH = PROJECT_ROOT / "ai" / "dataset" / "alpaca.jsonl"

def generate_dataset():
    if not DB_PATH.exists():
        print(f"Error: Database {DB_PATH.resolve()} not found.")
        return
    if not MEMORY_PATH.exists():
        print(f"Error: Memory file {MEMORY_PATH.resolve()} not found.")
        return

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cursor = conn.cursor()
    # Check if enter_tag exists in trades
    try:
        cursor.execute("SELECT pair, close_profit, enter_tag FROM trades WHERE is_open = 0")
        trades = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"SQLite Error: {e}")
        conn.close()
        return
    conn.close()

    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f: 
            memory = json.load(f)
    except Exception as e:
        print(f"Failed to read memory file: {e}")
        return

    decisions = {d["id"]: d for d in memory.get("decisions", [])}
    
    dataset = []
    for pair, profit, tag in trades:
        if not tag or "|" not in tag: 
            continue
        dec_id = tag.split("|")[0]
        if dec_id in decisions:
            dec = decisions[dec_id]
            is_winner = profit > 0
            
            # Formattazione Instruction stile V7
            instruction = f"{pair} RSI={dec.get('rsi_5m', 50)} MACD={dec.get('macd_5m', 0.0)} Fear={dec.get('fear_greed_value', 50)} Regime:{dec.get('market_regime', 'unknown')}"
            
            output_obj = {
                "decision": "BUY" if is_winner else "HOLD",
                "confidence": 82 if is_winner else 45,
                "thesis": dec.get("thesis", "") if is_winner else "Avoided to prevent drawdown.",
                "strategy": "V7_Base_Evolved"
            }
            
            dataset.append({
                "instruction": instruction,
                "input": "Evaluate market conditions and provide JSON decision.",
                "output": json.dumps(output_obj)
            })

    try:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            for entry in dataset: 
                f.write(json.dumps(entry) + "\n")
        print(f"Dataset generated globally: {len(dataset)} valid examples inside alpaca.jsonl")
    except Exception as e:
        print(f"Error creating output file: {e}")

if __name__ == "__main__": 
    generate_dataset()
