import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import Repository

def reset_supervisor():
    repo = Repository()
    
    current = repo.get_supervisor_controls()
    print(f"Current controls: {current}")
    
    new_controls = {
        "emergency_stop": 0,
        "max_open_trades": 3,
        "min_confidence": 70,
        "close_losers_threshold": -5.0,
        "ai_reasoning": "Manual Reset - Fixed NVIDIA configuration and logic"
    }
    
    repo.update_supervisor_controls(new_controls)
    print(f"New controls set: {new_controls}")

if __name__ == "__main__":
    reset_supervisor()
