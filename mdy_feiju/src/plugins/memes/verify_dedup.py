import sqlite3
import imagehash
from PIL import Image, ImageDraw
from io import BytesIO
import os

# Mock DB path
DB_PATH = "test_memes.db"

def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE libraries (id INTEGER PRIMARY KEY, group_id TEXT)")
    cursor.execute("CREATE TABLE images (id INTEGER PRIMARY KEY, library_id INTEGER, data BLOB, phash TEXT)")
    conn.commit()
    conn.close()

def get_dhash(img):
    return str(imagehash.dhash(img))

def test_deduplication():
    setup_db()
    
    # 1. Create a base image
    img1 = Image.new('RGB', (100, 100), color = 'red')
    d1 = ImageDraw.Draw(img1)
    d1.text((10,10), "Hello", fill=(255,255,0))
    
    buf1 = BytesIO()
    img1.save(buf1, format='PNG')
    data1 = buf1.getvalue()
    hash1 = get_dhash(img1)
    
    # Add to DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO libraries (id, group_id) VALUES (1, 'test_group')")
    cursor.execute("INSERT INTO images (library_id, data, phash) VALUES (1, ?, ?)", (data1, hash1))
    conn.commit()
    conn.close()
    
    print(f"Base image added. Hash: {hash1}")
    
    # 2. Check duplicate (Identical)
    # Should be True
    if check_duplicate_mock(1, hash1):
        print("PASS: Identical image detected as duplicate.")
    else:
        print("FAIL: Identical image NOT detected.")

    # 3. Check duplicate (Slightly modified - Resize)
    img2 = img1.resize((50, 50))
    hash2 = get_dhash(img2)
    print(f"Resized image hash: {hash2}")
    
    if check_duplicate_mock(1, hash2):
        print("PASS: Resized image detected as duplicate.")
    else:
        print("FAIL: Resized image NOT detected.")

    # 4. Check duplicate (Slightly modified - Crop)
    img3 = img1.crop((0, 0, 90, 90)) # Crop 10 pixels
    hash3 = get_dhash(img3)
    print(f"Cropped image hash: {hash3}")
    
    if check_duplicate_mock(1, hash3):
        print("PASS: Cropped image detected as duplicate.")
    else:
        print("FAIL: Cropped image NOT detected.")

    # 5. Check distinct image
    img4 = Image.new('RGB', (100, 100), color = 'blue')
    hash4 = get_dhash(img4)
    if not check_duplicate_mock(1, hash4):
        print("PASS: Distinct image NOT detected as duplicate.")
    else:
        print("FAIL: Distinct image detected as duplicate.")

def check_duplicate_mock(library_id, new_phash, threshold=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phash FROM images WHERE library_id = ?", (library_id,))
    images = cursor.fetchall()
    conn.close()
    
    new_hash_obj = imagehash.hex_to_hash(new_phash)
    
    for (img_phash,) in images:
        try:
            current_hash_obj = imagehash.hex_to_hash(img_phash)
            diff = new_hash_obj - current_hash_obj
            print(f"Comparing {new_phash} with {img_phash}: diff={diff}")
            if diff <= threshold:
                return True
        except Exception:
            continue
    return False

if __name__ == "__main__":
    try:
        test_deduplication()
    finally:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
