import sqlite3
import requests
import time

conn = sqlite3.connect('storage/v8_platform.sqlite')
conn.row_factory = sqlite3.Row

# Set up test data
strat_row = conn.execute("SELECT version_tag FROM strategy_versions WHERE status='candidate' OR status='keep_candidate' LIMIT 1").fetchone()
target_strat = strat_row['version_tag'] if strat_row else None

if target_strat:
    conn.execute("UPDATE strategy_versions SET status='validated' WHERE version_tag=?", (target_strat,))

model_tag = "qwen-trading-v8.3-1774870890"
conn.execute("UPDATE model_versions SET status='candidate' WHERE tag_name=?", (model_tag,))
conn.commit()

# Test 1: Blocked Model
print(f"Testing BLOCKED MODEL ({model_tag})...")
try:
    res1 = requests.post("http://127.0.0.1:8086/testlab/promote", json={"type": "model", "tag": model_tag})
    print(res1.json())
except Exception as e:
    print("API Error:", e)

# Test 2: Validated Strategy
if target_strat:
    print(f"\nTesting VALIDATED STRATEGY ({target_strat})...")
    try:
        res2 = requests.post("http://127.0.0.1:8086/testlab/promote", json={"type": "strategy", "tag": target_strat})
        print(res2.json())
    except Exception as e:
        print("API Error:", e)

# Check Audit Trail
print("\n=== AUDIT TRAIL (live_deployments) ===")
rows = conn.execute("SELECT * FROM live_deployments ORDER BY deployed_at DESC LIMIT 2").fetchall()
for r in rows:
    print(dict(r))

# Check final status
if target_strat:
    row = conn.execute("SELECT status FROM strategy_versions WHERE version_tag=?", (target_strat,)).fetchone()
    print(f"Final status of strategy {target_strat} in DB: {row['status']}")

conn.close()
