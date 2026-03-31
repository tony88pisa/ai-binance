import sqlite3
conn = sqlite3.connect('storage/v8_platform.sqlite')
conn.execute("DELETE FROM decisions WHERE action='hold'")
conn.commit()
from storage.repository import Repository
Repository()
