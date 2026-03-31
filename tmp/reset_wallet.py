import os
from pathlib import Path
import json
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import Repository

def reset_wallet():
    repo = Repository()
    state = repo.get_service_state("daemon")
    
    state_data = {}
    if state and state.get("state_json"):
        try:
            state_data = json.loads(state["state_json"])
        except Exception:
            pass
            
    old_wallet = state_data.get("wallet_eur", "Unknown")
    print(f"Valore wallet precedente: {old_wallet}")
    
    # Load .env
    load_dotenv(PROJECT_ROOT / ".env")
    initial_budget = float(os.getenv("INITIAL_CAPITAL", "10000.0"))
    
    # Aggiorna il wallet
    state_data["wallet_eur"] = initial_budget
    
    repo.update_service_heartbeat("daemon", json.dumps(state_data))
    print(f"Wallet resettato con successo a {initial_budget} nel database.")

if __name__ == "__main__":
    reset_wallet()
