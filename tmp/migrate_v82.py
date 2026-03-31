import sqlite3
import os

def migrate_v82():
    db_path = 'storage/v8_platform.sqlite'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Add columns to trade_outcomes
    try:
        cursor.execute("ALTER TABLE trade_outcomes ADD COLUMN exit_reason TEXT")
        print("Adde column exit_reason to trade_outcomes")
    except sqlite3.OperationalError:
        print("Column exit_reason already exists")

    try:
        cursor.execute("ALTER TABLE trade_outcomes ADD COLUMN nvidia_label TEXT")
        print("Added column nvidia_label to trade_outcomes")
    except sqlite3.OperationalError:
        print("Column nvidia_label already exists")
        
    # 2. Run schema.sql to pick up new tables (nvidia_reviews)
    schema_path = 'storage/schema.sql'
    if os.path.exists(schema_path):
        with open(schema_path, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
            print("Schema updated with new tables (IF NOT EXISTS)")
            
    conn.commit()
    conn.close()
    print("Migration V8.2 completed successfully.")

if __name__ == "__main__":
    migrate_v82()
