
import sqlite3
from pathlib import Path

DB_PATH = Path("data/shared_db/messages.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT timestamp, content FROM messages ORDER BY timestamp DESC LIMIT 20")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
