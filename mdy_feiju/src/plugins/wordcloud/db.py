import sqlite3
import time
from pathlib import Path
from typing import List, Tuple

# Define DB path
DB_PATH = Path("data/wordcloud")
DB_PATH.mkdir(parents=True, exist_ok=True)
DB_FILE = DB_PATH / "messages.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_message(group_id: str, user_id: str, content: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (group_id, user_id, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (group_id, user_id, content, int(time.time())))
    conn.commit()
    conn.close()

def get_today_messages(group_id: str) -> List[str]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get start of day timestamp
    now = time.localtime()
    start_of_day = int(time.mktime(time.struct_time((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))))
    
    cursor.execute("""
        SELECT content FROM messages
        WHERE group_id = ? AND timestamp >= ?
    """, (group_id, start_of_day))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [row[0] for row in rows]
