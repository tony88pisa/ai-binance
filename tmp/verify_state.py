import sys
from pathlib import Path
import json
import os
import sqlite3
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
from storage.repository import Repository

def verify():
    repo = Repository()
    repo._conn().row_factory = None # Reset if already custom
    with repo._conn() as conn:
        conn.row_factory = sqlite3.Row
        controls_row = conn.execute("SELECT * FROM supervisor_controls WHERE id=1").fetchone()
        controls = dict(controls_row) if controls_row else None
        
    if not controls:
        print("No supervisor_controls found in DB.")
        return
    
    print("=== VERIFICA COMPLETA ===")
    print(f"1. CURRENT SUPERVISOR STATUS: {'EMERGENCY_STOP ACTIVE' if controls.get('emergency_stop') else 'ONLINE (No Stop)'}")
    print(f"2. CURRENT NVIDIA MODEL: {os.getenv('NVIDIA_MODEL', 'Not found in ENV')}")
    print(f"3. CURRENT MIN_CONFIDENCE: {controls.get('min_confidence', 'N/A')}%")
    
    reasoning = controls.get('ai_reasoning', '')
    if "AI NVIDIA unavailable" in reasoning:
        print(f"4. FALLBACK SAFETY STATUS: ACTIVE ({reasoning})")
    else:
        print(f"4. FALLBACK SAFETY STATUS: INACTIVE (NVIDIA is connected)")
        
    print(f"5. LAST SUPERVISOR DECISIONS / LOG (ai_reasoning): {reasoning}")
    
    with repo._conn() as conn:
        conn.row_factory = sqlite3.Row
        print("--- LAST 5 SUPERVISOR LOG ENTRIES ---")
        logs = conn.execute("SELECT * FROM supervisor_logs ORDER BY id DESC LIMIT 5").fetchall()
        for l in logs:
            print(f"- [{l['timestamp']}] {l['ai_assessment']} | ACT: {l['actions_taken']} | Wallet: {l['wallet_state']}")

if __name__ == "__main__":
    verify()
