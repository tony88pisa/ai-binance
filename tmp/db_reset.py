import sqlite3
import os

DB_PATH = "storage/v8_platform.sqlite"

def reset_services():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Reset service_state in a way that allows the watcher to try again
    # We update the status to 'active' and could also reset config_json if it tracks restarts
    cur.execute("UPDATE service_state SET status='active' WHERE service_name='freqtrade'")
    cur.execute("UPDATE service_state SET status='active' WHERE service_name='evolution_loop'")
    
    conn.commit()
    conn.close()
    print("Database service_state Reset: COMPLETED.")

if __name__ == "__main__":
    reset_services()
