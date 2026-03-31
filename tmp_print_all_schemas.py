import sqlite3
c = sqlite3.connect('storage/v8_platform.sqlite')
tables = c.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()
for t in tables:
    print("---", t[0], "---")
    print(c.execute(f'SELECT sql FROM sqlite_master WHERE type="table" AND name="{t[0]}"').fetchone()[0])
