import sqlite3
c = sqlite3.connect('storage/v8_platform.sqlite')
print(c.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="service_state"').fetchone()[0])
