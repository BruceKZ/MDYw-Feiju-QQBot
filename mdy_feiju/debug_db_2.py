
import sqlite3
from pathlib import Path

# Use the copied debug DB
DB_PATH = Path("data/shared_db/debug_messages.db")
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, content FROM messages ORDER BY timestamp DESC LIMIT 20")
    rows = cursor.fetchall()
    for row in rows:
        print(f"TS: {row[0]}")
        print(f"Content: {row[1]}")
        print("-" * 20)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
