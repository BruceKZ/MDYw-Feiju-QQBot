
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

# We will use a separate database file for 2FA to keep it isolated
DB_FILE = Path("data/2fa.db")

def get_connection():
    """Get a connection to the 2FA database."""
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initialize the 2FA database tables."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        # Table for authorized users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authorized_users (
                user_id TEXT PRIMARY KEY
            )
        """)
        # Table for 2FA secrets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS secrets (
                name TEXT PRIMARY KEY,
                url TEXT,
                secret TEXT
            )
        """)
        conn.commit()

# User Management
def add_authorized_user(user_id: str):
    """Add a user to the authorized list."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO authorized_users (user_id) VALUES (?)", (user_id,))
        conn.commit()

def remove_authorized_user(user_id: str):
    """Remove a user from the authorized list."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM authorized_users WHERE user_id = ?", (user_id,))
        conn.commit()

def get_authorized_users() -> List[str]:
    """Get all authorized user IDs."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM authorized_users")
        return [row[0] for row in cursor.fetchall()]

def is_authorized(user_id: str) -> bool:
    """Check if a user is authorized."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM authorized_users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

# Secret Management
def add_secret(name: str, url: str, secret: str):
    """Add or update a 2FA secret."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO secrets (name, url, secret) VALUES (?, ?, ?)", (name, url, secret))
        conn.commit()

def get_secret(name: str) -> Optional[str]:
    """Get the secret for a given name."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT secret FROM secrets WHERE name = ?", (name,))
        row = cursor.fetchone()
        return row[0] if row else None

def get_all_secrets() -> List[Tuple[str, str, str]]:
    """Get all secrets (name, url, secret)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, url, secret FROM secrets")
        return cursor.fetchall()

def remove_secret(name: str):
    """"Remove a secret by name."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM secrets WHERE name = ?", (name,))
        conn.commit()
