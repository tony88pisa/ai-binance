import sys
from pathlib import Path
import json
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
from storage.repository import Repository

def verify():
    repo = Repository()
    controls = repo.get_supervisor_controls()
    
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
        print("--- LAST 5 SUPERVISOR LOG ENTRIES ---")
        logs = conn.execute("SELECT * FROM supervisor_logs ORDER BY id DESC LIMIT 5").fetchall()
        for l in logs:
            print(f"- [{l['created_at']}] {l['assessment']} | ACT: {l['actions']} | Wallet: {l['wallet_state']}")

if __name__ == "__main__":
    verify()
