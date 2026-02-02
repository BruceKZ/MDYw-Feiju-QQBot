from nonebot import on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from . import db

# Priority 10, not blocking other handlers
# Using logic: record every group message text
recorder = on_message(priority=10, block=False)

@recorder.handle()
async def _(event: GroupMessageEvent):
    msg = event.get_plaintext().strip()
    if not msg:
        return
        
    # Ignore commands (simplistic check)
    if msg.startswith(("/", "!", "！")):
        return
        
    db.save_message(str(event.group_id), str(event.user_id), msg)
