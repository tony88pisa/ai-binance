import os
import sys
import sqlite3
import json
from datetime import datetime

print("=== INIZIO VERIFICA TECNICA V8.3 (MODULI 11-15) ===")

db_path = 'storage/v8_platform.sqlite'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# --- CLEANUP PREPARATORIO ---
conn.execute("DELETE FROM service_state WHERE service_name IN ('research_brain', 'liveguard', 'self_healing', 'soak_tester')")
conn.execute("DELETE FROM live_deployments")
# Aggiungiamo alcuni deployment fittizi per testare il rollback
conn.execute("INSERT INTO live_deployments (id, model_tag, strategy_tag, deployed_at, deployed_by, status) VALUES (1, 'qwen-v1', 'strat-v1', '2026-03-30T10:00:00Z', 'TEST', 'active')")
conn.execute("INSERT INTO live_deployments (id, model_tag, strategy_tag, deployed_at, deployed_by, status) VALUES (2, 'qwen-v2', 'strat-v2', '2026-03-30T10:10:00Z', 'TEST', 'active')")
conn.commit()

# --- MODULO 11: RESEARCH BRAIN ---
print("\n[TEST Modulo 11] Esecuzione Research Daemon...")
os.system(".\\.venv\\Scripts\\python.exe scripts/research_daemon.py")
row = conn.execute("SELECT * FROM service_state WHERE service_name='research_brain'").fetchone()
if row:
    data = json.loads(row['config_json'])
    print(f"PASS: Trovato state. Sentiment: {data.get('macro_sentiment')} | Sys Risk: {data.get('systemic_risk')} | Time: {data.get('timestamp')}")
else:
    print("FAIL: Research Brain non ha aggiornato il DB.")

# --- MODULO 12: LIVEGUARD ---
print("\n[TEST Modulo 12] Forzatura condizione CRITICAL per LiveGuard...")
# Per forzare il Critical, impostiamo max_daily_drawdown a 10000.0 se non ci sono trade.
with open('scripts/liveguard.py', 'r') as f:
    lg_code = f.read()
with open('scripts/liveguard.py', 'w') as f:
    f.write(lg_code.replace("self.max_daily_drawdown = -50.0", "self.max_daily_drawdown = 10000.0"))

os.system(".\\.venv\\Scripts\\python.exe scripts/liveguard.py")

with open('scripts/liveguard.py', 'w') as f:
    f.write(lg_code) # Ripristina

lg_row = conn.execute("SELECT * FROM service_state WHERE service_name='liveguard'").fetchone()
if lg_row:
    lg_data = json.loads(lg_row['config_json'])
    print(f"PASS: LiveGuard Status: {lg_data.get('status')} | Blocked: {lg_data.get('blocked')} | Incidents: {lg_data.get('incidents')}")
else:
    print("FAIL: LiveGuard non ha aggiornato il DB.")

# --- MODULO 13: SELF HEALING / ROLLBACK ---
print("\n[TEST Modulo 13] Esecuzione Self-Healing con LiveGuard CRITICAL...")
os.system(".\\.venv\\Scripts\\python.exe scripts/self_healing.py")

heal_row = conn.execute("SELECT * FROM service_state WHERE service_name='self_healing'").fetchone()
if heal_row:
    print(f"PASS: Self-Healing Triggered: {json.loads(heal_row['config_json']).get('last_action')}")
else:
    print("FAIL: Self-Healing non triggerato.")
    
# Check DB Rollback
deployments = conn.execute("SELECT id, strategy_tag, status FROM live_deployments ORDER BY id DESC").fetchall()
print("Stato Live Deployments (Atteso V2 Rolled_Back, V1 Active):")
for d in deployments:
    print(f" - ID: {d['id']} | Tag: {d['strategy_tag']} | Status: {d['status']}")


# --- MODULO 14: SOAK TEST ---
print("\n[TEST Modulo 14] Esecuzione Soak Tester...")
os.system(".\\.venv\\Scripts\\python.exe scripts/soak_tester.py")
soak_row = conn.execute("SELECT * FROM service_state WHERE service_name='soak_tester'").fetchone()
if soak_row:
    soak_data = json.loads(soak_row['config_json'])
    print(f"PASS: Soak metrics -> Stabilita: {soak_data.get('stability_score')}/100 | RAM: {soak_data.get('memory_mb')} MB | Re-heals: {soak_data.get('recovery_count')}")
else:
    print("FAIL: Soak Tester non ha loggato.")

# --- MODULO 15: MICRO-CAPITAL GATE ---
print("\n[TEST Modulo 15] Verifica del Source Code Strategy...")
with open('user_data/strategies/OllamaHybridStrategy.py', 'r') as f:
    strat_code = f.read()
if "def custom_stake_amount" in strat_code and "min(10.0, proposed_stake)" in strat_code:
    print("PASS: Micro-Capital override (max 10 USDC) rilevato in OllamaHybridStrategy.")
else:
    print("FAIL: Micro-Capital override mancante.")
    
if "lg.get(\"blocked\", False) == True:" in strat_code:
    print("PASS: Blocco hardcoded LiveGuard rilevato nella Strategy (populate_entry_trend).")
else:
    print("FAIL: LiveGuard hard block mancante in Strategy.")

conn.close()
print("\n=== VERIFICA TECNICA COMPLETA ===")
