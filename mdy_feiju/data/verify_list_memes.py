import os
import sqlite3
from pathlib import Path
import asyncio

import sys
from pathlib import Path

# Add project root to path
# Local
PROJECT_ROOT_LOCAL = Path("d:/MDYw-Feiju-QQBot")
if PROJECT_ROOT_LOCAL.exists():
    sys.path.insert(0, str(PROJECT_ROOT_LOCAL))

# Docker
if Path("/app").exists():
    sys.path.insert(0, "/app")

# Set environment variable for test DB
TEST_DB_PATH = Path(__file__).parent / "test_memes.db"
os.environ["MEME_DB_PATH"] = str(TEST_DB_PATH)

try:
    import nonebot
    try:
        nonebot.init()
    except Exception:
        pass # Already initialized?

    try:
        from mdy_feiju.src.plugins.custom_memes import db, data_source
    except ImportError:
        # Fallback for Docker where src might be top level
        from src.plugins.custom_memes import db, data_source
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Helper to clear DB
def clear_db():
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)

async def test_list_memes():
    print(f"Using test DB: {TEST_DB_PATH}")
    clear_db()
    
    # Init DB
    db.init_db()
    
    group_id = "group_123"
    
    # Create some libraries
    print("Adding libraries...")
    db.create_library("foo", group_id)
    db.create_library("bar", group_id)
    db.create_library("baz", group_id)
    
    # Add an alias
    lib_id = db.get_library_id("foo", group_id)
    db.add_name_to_library("foo_alias", lib_id, group_id)
    
    # Add another group's library (should not show up)
    db.create_library("other_group_lib", "group_456")
    
    # Test get_all_memes
    print("Testing get_all_memes...")
    memes = data_source.MemeManager.get_all_memes(group_id)
    
    expected = ["bar", "baz", "foo", "foo_alias"]
    print(f"Result: {memes}")
    
    if sorted(memes) == sorted(expected):
        print("✅ Test Passed!")
    else:
        print(f"❌ Test Failed! Expected {expected}, got {memes}")
        
    clear_db()

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(test_list_memes())
        loop.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
