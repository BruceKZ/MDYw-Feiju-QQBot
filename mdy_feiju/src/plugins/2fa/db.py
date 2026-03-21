import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from .crypto import encrypt_secret, decrypt_secret, is_encrypted

logger = logging.getLogger(__name__)

# We will use a separate database file for 2FA to keep it isolated
DB_FILE = Path("data/2fa.db")

def get_connection():
    """Get a connection to the 2FA database."""
    return sqlite3.connect(DB_FILE)

def _migrate_encrypt_secrets(conn: sqlite3.Connection):
    """One-time migration: encrypt any plaintext secrets in the DB."""
    cursor = conn.cursor()
    cursor.execute("SELECT name, secret FROM secrets WHERE secret IS NOT NULL")
    rows = cursor.fetchall()
    migrated = 0
    for name, secret in rows:
        if not is_encrypted(secret):
            encrypted = encrypt_secret(secret)
            cursor.execute("UPDATE secrets SET secret = ? WHERE name = ?", (encrypted, name))
            migrated += 1
    if migrated:
        conn.commit()
        logger.info("Migrated %d plaintext secret(s) to encrypted storage.", migrated)

def init_db():
    """Initialize the 2FA database tables."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Table for 2FA secrets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS secrets (
                name TEXT PRIMARY KEY,
                url TEXT,
                secret TEXT,
                creator_id TEXT,
                note TEXT
            )
        """)
        
        cursor.execute("PRAGMA table_info(secrets)")
        columns_sec = [info[1] for info in cursor.fetchall()]
        if len(columns_sec) > 0 and 'creator_id' not in columns_sec:
            cursor.execute("DROP TABLE secrets")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS secrets (
                    name TEXT PRIMARY KEY,
                    url TEXT,
                    secret TEXT,
                    creator_id TEXT,
                    note TEXT
                )
            """)
        elif len(columns_sec) > 0 and 'note' not in columns_sec:
            cursor.execute("ALTER TABLE secrets ADD COLUMN note TEXT")

        # Table for permissions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                secret_name TEXT,
                user_id TEXT,
                alias TEXT,
                note TEXT,
                PRIMARY KEY (secret_name, user_id),
                UNIQUE (user_id, alias)
            )
        """)
        
        cursor.execute("PRAGMA table_info(permissions)")
        columns_perm = [info[1] for info in cursor.fetchall()]
        if len(columns_perm) > 0 and 'note' not in columns_perm:
            cursor.execute("ALTER TABLE permissions ADD COLUMN note TEXT")
            
        conn.commit()

        # Auto-migrate plaintext secrets to encrypted
        _migrate_encrypt_secrets(conn)

# Secret Management
def add_secret(name: str, url: str, secret: str, creator_id: str):
    """Add or update a 2FA secret. Name should be user_id_name format."""
    name = name.upper()
    encrypted = encrypt_secret(secret)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO secrets (name, url, secret, creator_id) VALUES (?, ?, ?, ?)", (name, url, encrypted, creator_id))
        conn.commit()

def delete_secret(name: str, user_id: str) -> bool:
    """Delete a secret or self-revoke a shared one."""
    name = name.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT creator_id FROM secrets WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return False
            
        if row[0] == user_id:
            cursor.execute("DELETE FROM secrets WHERE name = ?", (name,))
            cursor.execute("DELETE FROM permissions WHERE secret_name = ?", (name,))
            deleted = True
        else:
            cursor.execute("DELETE FROM permissions WHERE secret_name = ? AND user_id = ?", (name, user_id))
            deleted = cursor.rowcount > 0
            
        conn.commit()
        return deleted

def get_secret(name: str, user_id: str) -> Optional[str]:
    """Get the decrypted secret for a given name, only if user has access."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT secret, creator_id FROM secrets WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return None

        encrypted_secret, creator_id = row

        # Check access: must be creator or have permission
        if creator_id != user_id:
            cursor.execute("SELECT 1 FROM permissions WHERE secret_name = ? AND user_id = ?", (name, user_id))
            if not cursor.fetchone():
                return None

        return decrypt_secret(encrypted_secret)

def set_note(name: str, user_id: str, note: str) -> str:
    """Set a note for a secret."""
    name = name.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT creator_id FROM secrets WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return f"Failed: {name} not found."
            
        if row[0] == user_id:
            cursor.execute("UPDATE secrets SET note = ? WHERE name = ?", (note, name))
            conn.commit()
        else:
            cursor.execute("SELECT 1 FROM permissions WHERE secret_name = ? AND user_id = ?", (name, user_id))
            if not cursor.fetchone():
                return f"Failed: No permission for {name}."
            cursor.execute("UPDATE permissions SET note = ? WHERE secret_name = ? AND user_id = ?", (note, name, user_id))
            conn.commit()
            
        return f"Note set for {name}: {note}"

def clear_note(name: str, user_id: str) -> str:
    """Clear a note for a secret."""
    name = name.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT creator_id FROM secrets WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return f"Failed: {name} not found."
            
        if row[0] == user_id:
            cursor.execute("UPDATE secrets SET note = NULL WHERE name = ?", (name,))
            conn.commit()
        else:
            cursor.execute("SELECT 1 FROM permissions WHERE secret_name = ? AND user_id = ?", (name, user_id))
            if not cursor.fetchone():
                return f"Failed: No permission for {name}."
            cursor.execute("UPDATE permissions SET note = NULL WHERE secret_name = ? AND user_id = ?", (name, user_id))
            conn.commit()
            
        return f"Cleared note for {name}."

def get_note(name: str, user_id: str) -> str:
    """Get the note for a secret."""
    name = name.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT creator_id, note FROM secrets WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return f"Failed: {name} not found."
            
        if row[0] == user_id:
            note = row[1]
        else:
            cursor.execute("SELECT note FROM permissions WHERE secret_name = ? AND user_id = ?", (name, user_id))
            p_row = cursor.fetchone()
            if not p_row:
                return f"Failed: No permission for {name}."
            note = p_row[0]
            
        if not note:
            return f"{name} has no note."
        return f"Note for {name}: {note}"

# Permission Management
def grant_permission(secret_name: str, creator_id: str, target_qq: str) -> str:
    """Grants access to a secret. Returns a message indicating status."""
    secret_name = secret_name.upper()

    if not target_qq.isdigit():
        return "Failed: QQ号必须是纯数字。"

    with get_connection() as conn:
        cursor = conn.cursor()
        # Ensure creator_id actually owns this
        cursor.execute("SELECT 1 FROM secrets WHERE name = ? AND creator_id = ?", (secret_name, creator_id))
        if not cursor.fetchone():
            return f"Failed: Not found or not creator."
            
        cursor.execute("INSERT OR IGNORE INTO permissions (secret_name, user_id, alias, note) VALUES (?, ?, NULL, NULL)", (secret_name, target_qq))
        conn.commit()
        return f"Granted {target_qq} access to {secret_name}."

def revoke_permission(secret_name: str, creator_id: str, target_qq: str) -> str:
    """Revokes access from a secret."""
    secret_name = secret_name.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM secrets WHERE name = ? AND creator_id = ?", (secret_name, creator_id))
        if not cursor.fetchone():
            return f"Failed: Not found or not creator."
            
        cursor.execute("DELETE FROM permissions WHERE secret_name = ? AND user_id = ?", (secret_name, target_qq))
        conn.commit()
        return f"Revoked {target_qq}'s access to {secret_name}."

def set_alias(secret_name: str, user_id: str, alias: str) -> str:
    """Sets an alias for a shared secret."""
    secret_name = secret_name.upper()
    alias = alias.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM permissions WHERE secret_name = ? AND user_id = ?", (secret_name, user_id))
        if not cursor.fetchone():
            return f"Failed: No permission for {secret_name}."
            
        try:
            cursor.execute("UPDATE permissions SET alias = ? WHERE secret_name = ? AND user_id = ?", (alias, secret_name, user_id))
            conn.commit()
            return f"Alias '{alias}' set for {secret_name}."
        except sqlite3.IntegrityError:
            return f"Failed: Alias '{alias}' is already in use."

def resolve_secret_name(user_id: str, query: str) -> Optional[str]:
    """Resolves name to actual DB format."""
    query = query.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Exact match AND user is creator or has permission
        cursor.execute("SELECT name, creator_id FROM secrets WHERE name = ?", (query,))
        row = cursor.fetchone()
        if row:
            secret_name, creator_id = row
            if creator_id == user_id:
                return secret_name
            cursor.execute("SELECT 1 FROM permissions WHERE secret_name = ? AND user_id = ?", (secret_name, user_id))
            if cursor.fetchone():
                return secret_name
                
        # 2. Implicit match (user_id_query)
        implicit_name = f"{user_id}_{query}"
        cursor.execute("SELECT name FROM secrets WHERE name = ?", (implicit_name,))
        if cursor.fetchone():
            return implicit_name
            
        # 3. Alias match
        cursor.execute("SELECT secret_name FROM permissions WHERE user_id = ? AND alias = ?", (user_id, query))
        row = cursor.fetchone()
        if row:
            return row[0]
            
        return None

def get_all_user_secrets(user_id: str) -> str:
    """Returns a formatted string of all secrets accessible by the user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Created by user
        cursor.execute("SELECT name, note FROM secrets WHERE creator_id = ?", (user_id,))
        created = cursor.fetchall()
        
        # Shared with user
        cursor.execute("SELECT secret_name, alias, note FROM permissions WHERE user_id = ?", (user_id,))
        shared = cursor.fetchall()
        
        if not created and not shared:
            return "No 2FA keys."
            
        res = "2FA Keys:\n"
        if created:
            res += "[Created]\n"
            prefix = f"{user_id}_"
            for name, note in created:
                display_name = name.removeprefix(prefix)
                note_str = f" [Note: {note}]" if note else ""
                res += f"- {display_name}{note_str}\n"
            res += "\n"
        if shared:
            res += "[Shared with you]\n"
            for s_name, alias, note in shared:
                note_str = f" [Note: {note}]" if note else ""
                if alias:
                    res += f"- {alias} ({s_name}){note_str}\n"
                else:
                    res += f"- {s_name}{note_str}\n"
        return res.strip()
