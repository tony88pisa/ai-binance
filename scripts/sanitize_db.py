import sqlite3
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "storage" / "v8_platform.sqlite"

def sanitize():
    print(f"Sanitizing database at {DB_PATH}...")
    if not DB_PATH.exists():
        print("Database not found. Skipping.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Archive old V11 trades
    print("Archiving legacy V11 trades...")
    cur.execute("UPDATE decisions SET status = 'ARCHIVED' WHERE agent_name LIKE '%V11%' AND status NOT IN ('CLOSED', 'ARCHIVED')")
    archived_count = cur.rowcount
    
    # 2. Reset service states to force fresh heartbeats
    print("Resetting service states...")
    cur.execute("UPDATE service_state SET status = 'offline', last_heartbeat = ?", (datetime.now(timezone.utc).isoformat(),))

    # 3. Optional: Clear activity feed for a fresh start
    print("Clearing activity feed...")
    try:
        cur.execute("DELETE FROM agent_activity")
    except:
        pass

    conn.commit()
    conn.close()
    print(f"Sanitization complete. Archived {archived_count} ghost trades.")

if __name__ == "__main__":
    sanitize()
