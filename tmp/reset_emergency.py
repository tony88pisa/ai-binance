import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.repository import Repository

r = Repository()
r.update_supervisor_controls({
    "emergency_stop": 0,
    "max_open_trades": 3,
    "min_confidence": 70,
    "ai_reasoning": "Manual reset by operator"
})
c = r.get_supervisor_controls()
print(f"emergency_stop={c['emergency_stop']}, max_open_trades={c['max_open_trades']}, min_confidence={c['min_confidence']}")
print("SBLOCCO COMPLETATO")
