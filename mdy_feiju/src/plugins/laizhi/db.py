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
    
    # Create categories table with group_id
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        group_id TEXT NOT NULL,
        UNIQUE(name, group_id)
    )
    """)
    
    # Create images table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        data BLOB NOT NULL,
        phash TEXT NOT NULL,
        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()

def get_category_id(name: str, group_id: str) -> Optional[int]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM categories WHERE name = ? AND group_id = ?", (name, group_id))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def create_category(name: str, group_id: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name, group_id) VALUES (?, ?)", (name, group_id))
        category_id = cursor.lastrowid
        conn.commit()
        return category_id
    except sqlite3.IntegrityError:
        # Already exists
        conn.close()
        return get_category_id(name, group_id)
    finally:
        conn.close()

def add_image(category_id: int, data: bytes, phash: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO images (category_id, data, phash) VALUES (?, ?, ?)", (category_id, data, phash))
    conn.commit()
    conn.close()

def get_random_image(category_id: int) -> Optional[bytes]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Efficient random selection for SQLite
    cursor.execute("SELECT data FROM images WHERE category_id = ? ORDER BY RANDOM() LIMIT 1", (category_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_images_hashes(category_id: int) -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phash FROM images WHERE category_id = ?", (category_id,))
    results = cursor.fetchall()
    conn.close()
    return [r[0] for r in results]

def get_all_images(category_id: int) -> List[Tuple[bytes, str]]:
    """
    Get all images (data and hash) for a category.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT data, phash FROM images WHERE category_id = ?", (category_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def delete_image_by_hash(category_id: int, target_phash: str, threshold: int = 3) -> bool:
    """
    Finds an image in the category with a similar hash and deletes it.
    Returns True if deleted, False otherwise.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, phash FROM images WHERE category_id = ?", (category_id,))
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

def check_duplicate(category_id: int, new_phash: str, threshold: int = 3) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phash FROM images WHERE category_id = ?", (category_id,))
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

def migrate_lowercase_categories():
    """
    Migrate all category names to lowercase.
    If a lowercase category already exists, merge images into it.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get all categories
        cursor.execute("SELECT id, name, group_id FROM categories")
        categories = cursor.fetchall()
        
        for cat_id, name, group_id in categories:
            lower_name = name.lower()
            
            # If name is already lowercase, skip
            if name == lower_name:
                continue
                
            # Check if lowercase version exists
            cursor.execute("SELECT id FROM categories WHERE name = ? AND group_id = ?", (lower_name, group_id))
            existing = cursor.fetchone()
            
            if existing:
                target_id = existing[0]
                # Move images from current category to target category
                cursor.execute("UPDATE images SET category_id = ? WHERE category_id = ?", (target_id, cat_id))
                # Delete the old category
                cursor.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
                print(f"Merged '{name}' into '{lower_name}' for group {group_id}")
            else:
                # Just rename
                cursor.execute("UPDATE categories SET name = ? WHERE id = ?", (lower_name, cat_id))
                print(f"Renamed '{name}' to '{lower_name}' for group {group_id}")
                
        conn.commit()
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def resize_existing_images(max_dim: int = 512):
    """
    Resize all images in the database so that max(width, height) <= max_dim.
    Preserves format (GIF, PNG, JPEG).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, data FROM images")
        images = cursor.fetchall()
        
        count = 0
        for img_id, data in images:
            try:
                img = Image.open(BytesIO(data))
                format = img.format or "PNG"
                w, h = img.size
                
                if max(w, h) > max_dim:
                    # Calculate new size
                    ratio = max_dim / max(w, h)
                    new_size = (int(w * ratio), int(h * ratio))
                    
                    buf = BytesIO()
                    
                    if getattr(img, "is_animated", False):
                        # Handle GIF
                        frames = []
                        for frame in range(img.n_frames):
                            img.seek(frame)
                            # Resize frame
                            frame_img = img.copy()
                            frame_img.thumbnail(new_size)
                            frames.append(frame_img)
                        
                        # Save as GIF
                        frames[0].save(
                            buf, 
                            format="GIF", 
                            save_all=True, 
                            append_images=frames[1:], 
                            loop=img.info.get("loop", 0),
                            duration=img.info.get("duration", 100)
                        )
                    else:
                        # Handle static image
                        img.thumbnail(new_size)
                        img.save(buf, format=format)
                    
                    new_data = buf.getvalue()
                    
                    cursor.execute("UPDATE images SET data = ? WHERE id = ?", (new_data, img_id))
                    count += 1
            except Exception as e:
                print(f"Failed to resize image {img_id}: {e}")
                
        conn.commit()
        if count > 0:
            print(f"Resized {count} images to max dimension {max_dim}")
            
    except Exception as e:
        print(f"Resize migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()
