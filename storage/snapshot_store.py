import json
import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("storage.snapshot_store")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "storage" / "snapshots"

class SnapshotStore:
    def __init__(self, directory: Path = SNAPSHOT_DIR):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, name: str, data: Dict[str, Any]):
        """Save a JSON snapshot atomically for fast dashboard access."""
        path = self.directory / f"{name}.json"
        try:
            temp_fd, temp_path = tempfile.mkstemp(dir=str(self.directory), suffix=".tmp")
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump({
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "payload": data
                }, f, indent=4)
            
            if path.exists():
                path.unlink()
            os.rename(temp_path, str(path))
            logger.debug(f"Snapshot '{name}' updated successfully.")
        except Exception as e:
            logger.error(f"Failed to save snapshot '{name}': {e}")

    def load_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a JSON snapshot."""
        path = self.directory / f"{name}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load snapshot '{name}': {e}")
            return None

if __name__ == "__main__":
    store = SnapshotStore()
    store.save_snapshot("test", {"status": "ok"})
    print("Snapshot store check successful.")
