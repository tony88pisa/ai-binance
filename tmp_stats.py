import json
import sqlite3
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8087/health") as r:
        print("HEALTH:", json.dumps(json.loads(r.read()), indent=2))
except Exception as e:
    print("HEALTH ERROR:", e)

conn = sqlite3.connect('storage/v8_platform.sqlite')
print("--- SQLITE STATS ---")
hc = conn.execute("SELECT COUNT(*) FROM decisions WHERE action='hold';").fetchone()[0]
print("HOLD COUNT:", hc)
oc = conn.execute("SELECT COUNT(*) FROM trade_outcomes;").fetchone()[0]
print("OUTCOMES COUNT:", oc)
