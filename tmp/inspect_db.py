import sqlite3
import os

db_path = r"h:\ai-binance\storage\v8_platform.sqlite"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Elenco tabelle
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"TABELLE TROVATE: {tables}")
    
    # Ispezione schema per ogni tabella sospetta
    for table in tables:
        if "model" in table or "config" in table or "active" in table:
            cursor.execute(f"PRAGMA table_info({table})")
            schema = cursor.fetchall()
            print(f"\nSCHEMA PER {table}:")
            for col in schema:
                print(f"  - {col[1]} ({col[2]})")
    conn.close()
else:
    print(f"Errore: Database non trovato in {db_path} 🔴")
