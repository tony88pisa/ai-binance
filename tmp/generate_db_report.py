import sqlite3
import json
import os
from pathlib import Path

def generate_report():
    db_file = 'storage/v8_platform.sqlite'
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    
    report = []
    report.append(f"REAL DB FILE (B): {db_file}")
    
    # A. sqlite_master
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    table_names = [t['name'] for t in tables]
    report.append(f"TABLES FOUND: {table_names}")
    
    # PRAGMA table_info (A)
    for t in ['decisions', 'trade_outcomes', 'service_state', 'strategy_versions']:
        report.append(f"\n--- PRAGMA table_info({t}) ---")
        info = [dict(col) for col in conn.execute(f"PRAGMA table_info({t});").fetchall()]
        report.append(json.dumps(info, indent=2))
        
    # Real Row Evidence (C)
    report.append("\n--- REAL ROW EVIDENCE (C) ---")
    ss_row = conn.execute("SELECT * FROM service_state LIMIT 1;").fetchone()
    report.append(f"service_state: {json.dumps(dict(ss_row), indent=2) if ss_row else 'None'}")
    
    to_row = conn.execute("SELECT * FROM trade_outcomes LIMIT 1;").fetchone()
    report.append(f"trade_outcomes: {json.dumps(dict(to_row), indent=2) if to_row else 'None'}")
    
    sv_row = conn.execute("SELECT * FROM strategy_versions LIMIT 1;").fetchone()
    report.append(f"strategy_versions: {json.dumps(dict(sv_row), indent=2) if sv_row else 'None'}")
    
    with open('tmp/db_report.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(report))
    
    conn.close()

if __name__ == "__main__":
    generate_report()
