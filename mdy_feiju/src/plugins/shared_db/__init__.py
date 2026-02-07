
from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.log import logger

from . import db

driver = get_driver()

@driver.on_startup
async def _init():
    """Initialize database on startup"""
    try:
        db.init_db()
        # Cleanup old messages (keep 7 days)
        deleted = db.cleanup_old_messages(days=7)
        if deleted > 0:
            logger.info(f"[SharedDB] Cleaned up {deleted} old messages")
    except Exception as e:
        logger.error(f"[SharedDB] Database initialization failed: {e}")

# Message Recorder
# Priority 1 ensures it runs before most other matchers
message_recorder = on_message(priority=1, block=False)

@message_recorder.handle()
async def record_message(event: GroupMessageEvent):
    """
    Record all group messages to the shared database.
    Stores the full raw message (CQ codes included) to support re-sending (e.g. for anti-recall).
    """
    try:
        import json
        
        # Serialize message segments to JSON for robust storage
        # This handles images, forwards, shares, etc. more reliably than raw CQ strings
        content_json = json.dumps([seg.__dict__ for seg in event.message], default=str)

        # Save to DB
        # Note: OneBot v11 message_id is int, convert to str
        db.save_message(
            group_id=str(event.group_id),
            user_id=str(event.user_id),
            message_id=str(event.message_id),
            content=content_json
        )
    except Exception as e:
        logger.error(f"[SharedDB] Failed to save message: {e}")

# Export common functions for other plugins
__all__ = ["db"]
