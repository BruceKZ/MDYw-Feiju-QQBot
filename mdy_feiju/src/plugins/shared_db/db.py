
import sqlite3
import time
import shutil
from pathlib import Path
from contextlib import contextmanager
from typing import List, Optional, Tuple

from .config import DATA_DIR, DB_FILE, WORDCLOUD_DB_FILE
from nonebot.log import logger

@contextmanager
def get_connection():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database and migrate if needed"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Migration: Move old wordcloud DB if exists and new DB doesn't
    if WORDCLOUD_DB_FILE.exists() and not DB_FILE.exists():
        try:
            shutil.copy2(WORDCLOUD_DB_FILE, DB_FILE)
            logger.info(f"[SharedDB] Migrated database from {WORDCLOUD_DB_FILE}")
        except Exception as e:
            logger.error(f"[SharedDB] Failed to migrate database: {e}")

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Ensure messages table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)
        
        # 2. Check for message_id column
        cursor.execute("PRAGMA table_info(messages)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "message_id" not in columns:
            logger.info("[SharedDB] Adding message_id column to messages table")
            cursor.execute("ALTER TABLE messages ADD COLUMN message_id TEXT")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_id ON messages (message_id)")

        # 3. Create monitored_users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitored_users (
                group_id TEXT NOT NULL,
                target_user_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (group_id, target_user_id)
            )
        """)
        
        # indices
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_timestamp 
            ON messages (group_id, timestamp)
        """)
        
        conn.commit()
    logger.info("[SharedDB] Database initialized")

def save_message(group_id: str, user_id: str, message_id: str, content: str):
    """Save group message to database"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (group_id, user_id, message_id, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (group_id, user_id, message_id, content, int(time.time()))
        )
        conn.commit()

def get_message_by_id(message_id: str) -> Optional[str]:
    """Retrieve message content by valid message_id"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM messages WHERE message_id = ?",
            (message_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

def get_message_details(message_id: str) -> Optional[Tuple[str, str]]:
    """Retrieve message details (user_id, content) by valid message_id"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, content FROM messages WHERE message_id = ?",
            (message_id,)
        )
        row = cursor.fetchone()
        return row if row else None

def get_messages_last_24h(group_id: str) -> List[str]:
    """Get messages from last 24h for wordcloud"""
    cutoff_time = int(time.time()) - 86400
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM messages WHERE group_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
            (group_id, cutoff_time)
        )
        rows = cursor.fetchall()
    return [row[0] for row in rows]

def cleanup_old_messages(days: int = 7):
    """Cleanup old messages"""
    cutoff_time = int(time.time()) - (days * 86400)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_time,))
        deleted = cursor.rowcount
        conn.commit()
    return deleted

# Monitor Management
def add_monitor(group_id: str, target_user_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO monitored_users (group_id, target_user_id, created_at) VALUES (?, ?, ?)",
            (group_id, target_user_id, int(time.time()))
        )
        conn.commit()

def remove_monitor(group_id: str, target_user_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM monitored_users WHERE group_id = ? AND target_user_id = ?",
            (group_id, target_user_id)
        )
        conn.commit()

def is_monitored(group_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM monitored_users WHERE group_id = ? AND target_user_id = ?",
            (group_id, user_id)
        )
        return cursor.fetchone() is not None

def get_monitored_users(group_id: str) -> List[str]:
    """Get list of monitored user IDs in a group"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT target_user_id FROM monitored_users WHERE group_id = ?",
            (group_id,)
        )
        return [row[0] for row in cursor.fetchall()]
