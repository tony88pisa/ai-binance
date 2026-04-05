import sqlite3
conn = sqlite3.connect('H:/ai-binance/storage/v8_platform.sqlite')
conn.row_factory = sqlite3.Row

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('TABLES:')
for t in tables:
    print(f'  {t}')
print()

for t in ['trade_outcomes', 'decisions']:
    print(f'=== {t} ===')
    cols = conn.execute(f'PRAGMA table_info({t})').fetchall()
    for r in cols:
        print(f'  col: {r[1]} ({r[2]})')
    print()

conn.close()
