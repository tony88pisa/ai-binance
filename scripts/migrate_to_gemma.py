import sqlite3
import os
import sys

def migrate():
    db_path = r"h:\ai-binance\storage\v8_platform.sqlite"
    if not os.path.exists(db_path):
        print(f"Errore: Database non trovato in {db_path} 🔴")
        sys.exit(1)

    print(f"Inizio migrazione a Gemma 4:E4B su {db_path}... 🚀")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        model_name = "gemma4:e4b"
        
        # 1. Register in model_versions (Senza duplicati)
        cursor.execute("SELECT tag_name FROM model_versions WHERE tag_name = ?", (model_name,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO model_versions (tag_name, parent_tag, base_model, dataset_id, status, trained_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (model_name, "legacy", "gemma4", "training_april_2026", "approved"))
            print(f"Modello {model_name} registrato in model_versions.")

        # 2. Update Live Deployment
        # Disattiva deploy precedenti
        cursor.execute("UPDATE live_deployments SET status = 'inactive' WHERE status = 'active'")
        
        # Inserisce nuovo deploy Gemma 4
        cursor.execute("""
            INSERT INTO live_deployments (model_tag, strategy_tag, deployed_at, deployed_by, status)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
        """, (model_name, "standard_moe_v8", "Antigravity_AI", "active"))
        
        conn.commit()
        print(f"Migrazione completata! ✅ RTX 5080 pronta con {model_name}")
        
    except Exception as e:
        conn.rollback()
        print(f"Errore durante la migrazione: {e} 🔴")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
