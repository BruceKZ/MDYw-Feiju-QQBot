from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment
from nonebot.matcher import Matcher
from . import db, recorder, generator

# Initialize DB
driver = get_driver()
driver.on_startup(db.init_db)

# Command: /词云 (Only allow exactly "词云" command name)
wordcloud_cmd = on_command("词云", priority=5, block=True)

@wordcloud_cmd.handle()
async def _(matcher: Matcher, event: GroupMessageEvent):
    group_id = str(event.group_id)
    
    # Get messages
    messages = db.get_today_messages(group_id)
    
    if not messages:
        await matcher.finish("今天群里还没人说话呢，生成不了词云！")
        
    # Generate image
    img_bytes = generator.generate_word_cloud(messages)
    
    if not img_bytes:
        await matcher.finish("生成失败，可能是消息太少或者没有有效关键词。")

    await matcher.finish(MessageSegment.image(img_bytes))
