# -*- coding: utf-8 -*-
"""
数据持久化层
SQLite storage for group messages with 24-hour rolling window
"""
import sqlite3
import time
from pathlib import Path
from typing import List
from contextlib import contextmanager

from .config import DATA_DIR, DB_FILE


def init_db():
    """初始化数据库和表结构"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with get_connection() as conn:
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
        # 创建索引以加速查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_timestamp 
            ON messages (group_id, timestamp)
        """)
        conn.commit()


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()


def save_message(group_id: str, user_id: str, content: str):
    """保存群消息到数据库"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (group_id, user_id, content, timestamp) VALUES (?, ?, ?, ?)",
            (group_id, user_id, content, int(time.time()))
        )
        conn.commit()


def get_messages_last_24h(group_id: str) -> List[str]:
    """
    获取过去24小时内的群消息
    使用滚动窗口，确保随时调用都能获取足够数据
    """
    cutoff_time = int(time.time()) - 86400  # 24小时 = 86400秒
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM messages WHERE group_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
            (group_id, cutoff_time)
        )
        rows = cursor.fetchall()
    
    return [row[0] for row in rows]


def get_message_count(group_id: str) -> int:
    """获取过去24小时消息数量"""
    cutoff_time = int(time.time()) - 86400
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE group_id = ? AND timestamp >= ?",
            (group_id, cutoff_time)
        )
        return cursor.fetchone()[0]


def cleanup_old_messages(days: int = 7):
    """
    清理指定天数之前的旧消息
    建议通过 APScheduler 或启动时调用
    """
    cutoff_time = int(time.time()) - (days * 86400)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM messages WHERE timestamp < ?",
            (cutoff_time,)
        )
        deleted = cursor.rowcount
        conn.commit()
    
    return deleted
