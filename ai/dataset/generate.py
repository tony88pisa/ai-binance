import sqlite3
import json
from pathlib import Path

import os
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "storage" / "v8_platform.sqlite"
MEMORY_PATH = PROJECT_ROOT / "user_data" / "memory_v2.json"
OUTPUT_PATH = PROJECT_ROOT / "ai" / "dataset" / "alpaca.jsonl"

def generate_dataset():
    # --- 1. COLLECT CRYPTO DATA ---
    current_db = DB_PATH
    if not current_db.exists():
        print(f"Database {current_db.resolve()} not found. Checking storage...")
        current_db = PROJECT_ROOT / "storage" / "v8_platform.sqlite"
        if not current_db.exists(): 
            print("Error: No valid database found.")
            return
    
    if not MEMORY_PATH.exists():
        print(f"Error: Memory file {MEMORY_PATH.resolve()} not found.")
        return
    
    conn = sqlite3.connect(f"file:{current_db}?mode=ro", uri=True)
    cursor = conn.cursor()
    trade_rows = []
    try:
        # Recuperiamo la storia reale unendo decisioni e esiti
        query = """
            SELECT d.asset, o.realized_pnl_pct, d.thesis, d.regime
            FROM decisions d
            JOIN trade_outcomes o ON d.id = o.decision_id
            WHERE d.thesis IS NOT NULL
            LIMIT 500
        """
        cursor.execute(query)
        trade_rows = cursor.fetchall()
    except Exception as e:
        print(f"Crypto DB Error (v8_platform): {e}")
    conn.close()

    # --- 2. COLLECT TRADFI DATA (GOLD) ---
    # Sibling directory check: H:/ai-binance -> H:/ai-tradfi-parallel
    TRADFI_DB = PROJECT_ROOT.parent / "ai-tradfi-parallel" / "tradfi_history.sqlite"
    tradfi_rows = []
    if TRADFI_DB.exists():
        try:
            conn_tf = sqlite3.connect(f"file:{TRADFI_DB}?mode=ro", uri=True)
            # Find Executed Trades in TradFi History
            tradfi_rows = conn_tf.execute("SELECT data, timestamp FROM history WHERE agent != 'Analyst' AND action = 'EXECUTED' LIMIT 100").fetchall()
            conn_tf.close()
        except Exception as e:
            print(f"TradFi DB Warning: {e}")

    # --- 3. MERGE & FORMAT ---
    dataset = []
    
    # Format Crypto
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f: memory = json.load(f)
        decisions = {d["id"]: d for d in memory.get("decisions", [])}
    except: decisions = {}

    for asset, pnl, thesis, regime in trade_rows:
        is_winner = pnl > 0
        dataset.append({
            "instruction": f"Asset={asset} Regime={regime}",
            "input": f"Market analysis: {thesis}",
            "output": json.dumps({
                "decision": "BUY" if is_winner else "HOLD", 
                "confidence": 92 if is_winner else 45, 
                "strategy": "NVIDIA_Evolved_V11"
            })
        })

    # Format Gold
    for data_json, ts in tradfi_rows:
        try:
            d = json.loads(data_json)
            # Simulated success for training
            dataset.append({
                "instruction": f"XAU_USD GOLD Session={ts}",
                "input": "Evaluate Gold stability.",
                "output": json.dumps({"decision": "BUY", "confidence": 88, "strategy": "Gold_Sandbox_V1"})
            })
        except: continue

    try:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            for entry in dataset: f.write(json.dumps(entry) + "\n")
        print(f"Dual-Project Dataset generated: {len(dataset)} examples (Crypto + Gold)")
    except Exception as e:
        print(f"Error creating output file: {e}")

if __name__ == "__main__": 
    generate_dataset()
