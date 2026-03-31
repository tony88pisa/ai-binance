import os
import sqlite3
import subprocess
import socket
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def _load_env():
    """Load .env if vars not already set."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v

_load_env()

class AITelemetry:
    def __init__(self, db_path="storage/v8_platform.sqlite"):
        self.db_path = PROJECT_ROOT / db_path

    def get_local_brain_status(self):
        default = {"status": "UNKNOWN", "model": os.getenv("OLLAMA_MODEL", "N/D"), "size": "N/D", "processor": "N/D"}
        try:
            res = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                lines = res.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    return {"status": "RUNNING (VRAM)", "model": parts[0], "size": parts[2] if len(parts) > 2 else "?", "processor": parts[3] if len(parts) > 3 else "GPU"}
                return {"status": "IDLE (Configured)", "model": os.getenv("OLLAMA_MODEL", "N/D"), "size": "N/D", "processor": "N/D"}
        except Exception:
            pass
        return default

    def get_teacher_brain_status(self):
        status = {"enabled": os.getenv("NVIDIA_ENABLED", "false").lower() == "true", "last_review_at": "MAI", "last_review_id": "Nessuna", "budget_status": "DISABLED", "candidates_count": 0, "last_error": "Nessuno"}
        if not status["enabled"]:
            return status
        status["budget_status"] = "OK"
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            rev = conn.execute("SELECT review_id, created_at FROM nvidia_reviews ORDER BY created_at DESC LIMIT 1").fetchone()
            if rev:
                status["last_review_at"] = rev["created_at"]
                status["last_review_id"] = rev["review_id"]
            cand = conn.execute("SELECT COUNT(*) as c FROM strategy_versions WHERE family LIKE '%Nvidia%' AND status = 'candidate'").fetchone()
            status["candidates_count"] = cand["c"] if cand else 0
            conn.close()
        except Exception as e:
            status["last_error"] = str(e)[:50]
        return status

    def get_system_phase(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', 8080)) == 0:
                    return "LIVE (Execution)"
        except Exception:
            pass
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT status FROM service_state WHERE service_name = 'evolution_loop'").fetchone()
            if row and row["status"] == "active":
                return "POST-MARKET (Analysis)"
            conn.close()
        except Exception:
            pass
        return "IDLE / TESTLAB"
