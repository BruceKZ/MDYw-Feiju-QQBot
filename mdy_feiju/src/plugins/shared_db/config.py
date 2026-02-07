from pathlib import Path

# DB config
DATA_DIR = Path("data/shared_db")
DB_FILE = DATA_DIR / "messages.db"

# Legacy wordcloud DB (for migration)
WORDCLOUD_DB_FILE = Path("data/wordcloud/messages.db")
