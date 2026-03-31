import sqlite3
import json
import os
import requests
from pathlib import Path

DB_PATH = Path("H:/ai binance/storage/v8_platform.sqlite")

def check_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    print("--- TABLES ---")
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur]
    print(tables)
    
    for t in ['servicestate', 'service_state', 'nvidia_reviews']:
        if t in tables:
            print(f"\n--- SCHEMA: {t} ---")
            cur = conn.execute(f"PRAGMA table_info({t})")
            print([dict(r) for r in cur])
            print(f"\n--- DATA: {t} ---")
            cur = conn.execute(f"SELECT * FROM {t} LIMIT 5")
            print([dict(r) for r in cur])
    conn.close()

def check_telemetry():
    print("\n--- TELEMETRY CHECK ---")
    try:
        from ai.ai_telemetry import AITelemetry
        tel = AITelemetry()
        print(f"Local Brain: {tel.get_local_brain_status()}")
        print(f"Teacher Brain: {tel.get_teacher_brain_status()}")
        print(f"System Phase: {tel.get_system_phase()}")
    except Exception as e:
        print(f"Telemetry Error: {e}")

if __name__ == "__main__":
    check_db()
    check_telemetry()
