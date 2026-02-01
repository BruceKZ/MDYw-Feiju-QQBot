import sqlite3
import imagehash
import os
from pathlib import Path
from typing import Optional, List, Tuple
from PIL import Image
from io import BytesIO

# Use environment variable for DB path if set, otherwise default to local file
env_db_path = os.getenv("MEME_DB_PATH")
if env_db_path:
    DB_PATH = Path(env_db_path)
else:
    DB_PATH = Path(__file__).parent / "memes.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if migration is needed (if old tables exist)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
    if cursor.fetchone():
        print("Detected legacy schema (categories). Starting migration...")
        migrate_v2(conn)
    else:
        # Create libraries table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS libraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL
        )
        """)
        
        # Create naming table (maps names to libraries)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS names (
            name TEXT NOT NULL,
            library_id INTEGER NOT NULL,
            group_id TEXT NOT NULL,
            PRIMARY KEY (name, group_id),
            FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
        """)
        
        # Create images table (Note: category_id is preserved as column name to minimize change, but refers to library_id)
        # Or better, let's rename it to library_id for clarity. RENAME COLUMN is supported in newer SQLite.
        # But if we create new, let's use library_id.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            data BLOB NOT NULL,
            phash TEXT NOT NULL,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
        """)
    
    conn.commit()
    conn.close()

def migrate_v2(conn: sqlite3.Connection):
    """
    Migrate from old schema (categories, aliases, images.category_id) 
    to new schema (libraries, names, images.library_id).
    """
    cursor = conn.cursor()
    try:
        # 1. Create new tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS libraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS names (
            name TEXT NOT NULL,
            library_id INTEGER NOT NULL,
            group_id TEXT NOT NULL,
            PRIMARY KEY (name, group_id),
            FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
        """)
        
        # 2. Migrate categories -> libraries + names
        cursor.execute("SELECT id, name, group_id FROM categories")
        categories = cursor.fetchall()
        
        for cat_id, name, group_id in categories:
            # We preserve ID if possible to avoid updating images, but let's be safe.
            # Insert into libraries with explicit ID
            cursor.execute("INSERT INTO libraries (id, group_id) VALUES (?, ?)", (cat_id, group_id))
            # Insert into names
            cursor.execute("INSERT INTO names (name, library_id, group_id) VALUES (?, ?, ?)", (name, cat_id, group_id))
            
        # 3. Migrate aliases -> names
        # Check if aliases table exists (it might not if very old version, but we added it recently)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='aliases'")
        if cursor.fetchone():
            cursor.execute("SELECT alias_name, category_id, group_id FROM aliases")
            aliases = cursor.fetchall()
            for alias_name, cat_id, group_id in aliases:
                # Aliases might duplicate real names in other groups, but (name, group) is PK.
                try:
                    cursor.execute("INSERT INTO names (name, library_id, group_id) VALUES (?, ?, ?)", (alias_name, cat_id, group_id))
                except sqlite3.IntegrityError:
                    print(f"Skipping duplicate alias migration: {alias_name} in {group_id}")

        # 4. Migrate images table
        # We need to rename category_id to library_id.
        # SQLite < 3.25 doesn't support RENAME COLUMN.
        # Easier: Create new images table, copy data, drop old.
        cursor.execute("""
        CREATE TABLE images_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            data BLOB NOT NULL,
            phash TEXT NOT NULL,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
        """)
        
        cursor.execute("SELECT id, category_id, data, phash FROM images")
        images = cursor.fetchall()
        cursor.executemany("INSERT INTO images_new (id, library_id, data, phash) VALUES (?, ?, ?, ?)", images)
        
        # 5. Drop old tables
        cursor.execute("DROP TABLE images")
        cursor.execute("DROP TABLE categories")
        cursor.execute("DROP TABLE IF EXISTS aliases")
        
        # 6. Rename new images table
        cursor.execute("ALTER TABLE images_new RENAME TO images")
        
        print("Migration to V2 (Libraries/Names) completed successfully.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise e

# --- New API ---

def get_library_id(name: str, group_id: str) -> Optional[int]:
    """Get library ID by name (alias or real name)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT library_id FROM names WHERE name = ? AND group_id = ?", (name, group_id))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def create_library(name: str, group_id: str) -> int:
    """Create a new library with a primary name."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Create library
        cursor.execute("INSERT INTO libraries (group_id) VALUES (?)", (group_id,))
        lib_id = cursor.lastrowid
        
        # Create name
        cursor.execute("INSERT INTO names (name, library_id, group_id) VALUES (?, ?, ?)", (name, lib_id, group_id))
        conn.commit()
        return lib_id
    except sqlite3.IntegrityError:
        # Name exists?
        conn.close()
        return get_library_id(name, group_id)
    finally:
        conn.close()

def add_name_to_library(name: str, library_id: int, group_id: str) -> bool:
    """Add a new name (alias) to an existing library."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO names (name, library_id, group_id) VALUES (?, ?, ?)", (name, library_id, group_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_name(name: str, group_id: str) -> bool:
    """Remove a name from the system."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM names WHERE name = ? AND group_id = ?", (name, group_id))
    rows = cursor.rowcount
    conn.commit()
    conn.close()
    return rows > 0

def merge_libraries(src_lib_id: int, dest_lib_id: int):
    """
    Merge src library into dest library.
    Moves all images and names from src to dest, then deletes src.
    """
    if src_lib_id == dest_lib_id:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # 1. Move Images
        cursor.execute("UPDATE images SET library_id = ? WHERE library_id = ?", (dest_lib_id, src_lib_id))
        
        # 2. Move Names (Handle conflicts? Unique(name, group_id) shouldn't conflict because names imply different libs in same group)
        cursor.execute("UPDATE names SET library_id = ? WHERE library_id = ?", (dest_lib_id, src_lib_id))
        
        # 3. Delete Src Library
        cursor.execute("DELETE FROM libraries WHERE id = ?", (src_lib_id,))
        
        conn.commit()
    finally:
        conn.close()

def get_library_names(library_id: int) -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM names WHERE library_id = ?", (library_id,))
    results = cursor.fetchall()
    conn.close()
    return [r[0] for r in results]

# --- Image Operations (Updated for library_id) ---

def add_image(library_id: int, data: bytes, phash: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO images (library_id, data, phash) VALUES (?, ?, ?)", (library_id, data, phash))
    conn.commit()
    conn.close()

def get_random_image(library_id: int) -> Optional[bytes]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM images WHERE library_id = ? ORDER BY RANDOM() LIMIT 1", (library_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_images(library_id: int) -> List[Tuple[bytes, str]]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT data, phash FROM images WHERE library_id = ?", (library_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def check_duplicate(library_id: int, new_phash: str, threshold: int = 3) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phash FROM images WHERE library_id = ?", (library_id,))
    images = cursor.fetchall()
    conn.close()
    
    new_hash_obj = imagehash.hex_to_hash(new_phash)
    
    for (img_phash,) in images:
        try:
            current_hash_obj = imagehash.hex_to_hash(img_phash)
            if new_hash_obj - current_hash_obj <= threshold:
                return True
        except Exception:
            continue
            
    return False

def delete_image_by_hash(library_id: int, target_phash: str, threshold: int = 3) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, phash FROM images WHERE library_id = ?", (library_id,))
    images = cursor.fetchall()
    
    target_hash_obj = imagehash.hex_to_hash(target_phash)
    
    for img_id, img_phash in images:
        try:
            current_hash_obj = imagehash.hex_to_hash(img_phash)
            if target_hash_obj - current_hash_obj <= threshold:
                cursor.execute("DELETE FROM images WHERE id = ?", (img_id,))
                conn.commit()
                conn.close()
                return True
        except Exception:
            continue
            
    conn.close()
    return False

def migrate_lowercase_categories():
    # Deprecated or update logic?
    # Logic: Make all names lowercase. If conflicts, merge libraries.
    # We can implement this on startup if needed.
    pass

def resize_existing_images(max_dim: int = 512):
    # Same as before but use library_id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, data FROM images")
        images = cursor.fetchall()
        
        count = 0
        for img_id, data in images:
            # ... (Resize logic same as before) ...
            try:
                img = Image.open(BytesIO(data))
                format = img.format or "PNG"
                w, h = img.size
                
                if max(w, h) > max_dim:
                    ratio = max_dim / max(w, h)
                    new_size = (int(w * ratio), int(h * ratio))
                    buf = BytesIO()
                    
                    if getattr(img, "is_animated", False):
                        frames = []
                        for frame in range(img.n_frames):
                            img.seek(frame)
                            frame_img = img.copy()
                            frame_img.thumbnail(new_size)
                            frames.append(frame_img)
                        frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], loop=img.info.get("loop", 0), duration=img.info.get("duration", 100))
                    else:
                        img.thumbnail(new_size)
                        img.save(buf, format=format)
                    
                    new_data = buf.getvalue()
                    cursor.execute("UPDATE images SET data = ? WHERE id = ?", (new_data, img_id))
                    count += 1
            except Exception:
                pass
                
        conn.commit()
    finally:
        conn.close()
