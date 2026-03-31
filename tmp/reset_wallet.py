import sys
from pathlib import Path
import json

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
    
    # Aggiorna il wallet
    state_data["wallet_eur"] = 50.0
    
    repo.update_service_heartbeat("daemon", json.dumps(state_data))
    print("Wallet resettato con successo a 50.0 EUR nel database.")

if __name__ == "__main__":
    reset_wallet()
