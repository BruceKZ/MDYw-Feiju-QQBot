import re
import json
import base64
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, PrivateMessageEvent, MessageSegment, Message
from nonebot.matcher import Matcher
from nonebot import get_driver

from . import db
from .utils import get_context_id, MAX_DIMENSION
from .data_source import MemeManager

async def init_data():
    db.init_db()
    db.migrate_lowercase_categories()
    db.resize_existing_images(MAX_DIMENSION)

async def handle_get_meme(matcher: Matcher, event: MessageEvent):
    msg = event.get_plaintext().strip()
    match = re.match(r"^来[只个点之](.+)$", msg)
    if not match:
        return
    
    raw_text = match.group(1).strip()
    context_id = get_context_id(event)
    
    result, matched_name = MemeManager.get_meme(raw_text, context_id)
    
    if not matched_name:
        await matcher.finish(f"一张{raw_text}都没有，来鸡毛？")

    if not result:
        await matcher.finish(f"一张{matched_name}都没有，来鸡毛？")
        
    await matcher.finish(result)

async def handle_add_meme(matcher: Matcher, bot: Bot, event: MessageEvent):
    msg = event.get_plaintext().strip()
    # Remove prefix "添加"
    category_name = msg[2:].strip()
    if not category_name:
        return

    # Check for --force flag
    force = False
    if "--force" in category_name:
        force = True
        category_name = category_name.replace("--force", "").strip()
    
    if not category_name:
        return

    if not event.reply:
        return

    reply_msg = event.reply.message
    # No longer require images check here, as we support text

    context_id = get_context_id(event)
    result_msg, dup_img = await MemeManager.add_meme(category_name, reply_msg, context_id, force=force)
    
    if dup_img:
        # If duplicate found, send message with the conflicting original image/content
        # Check if dup_img is JSON (mixed) or bytes (image)
        try:
             # Try to parse as JSON list
            content = json.loads(dup_img.decode("utf-8"))
            if isinstance(content, list):
                 # Construct message
                 dup_msg = Message()
                 for seg in content:
                    if seg["type"] == "text":
                        dup_msg.append(MessageSegment.text(seg["data"]["text"]))
                    elif seg["type"] == "image":
                        img_bytes = base64.b64decode(seg["data"]["file"])
                        dup_msg.append(MessageSegment.image(img_bytes))
                 await matcher.finish(result_msg + dup_msg)
                 return
        except Exception:
            pass
            
        # Fallback to pure image
        await matcher.finish(result_msg + MessageSegment.image(dup_img))
    else:
        await matcher.finish(result_msg)

async def handle_delete_meme(matcher: Matcher, bot: Bot, event: MessageEvent):
    msg = event.get_plaintext().strip()
    category_name = msg[2:].strip()
    
    if not category_name:
        return

    if not event.reply:
        await matcher.finish("删哪个")
        return

    if str(event.reply.sender.user_id) != str(bot.self_id):
        await matcher.finish("不是我发的你让我删？")
        return

    reply_msg = event.reply.message
    # No longer require images check here

    context_id = get_context_id(event)
    # Pass message object directly
    result = await MemeManager.delete_meme(category_name, reply_msg, context_id)
    await matcher.finish(result)

async def handle_sync(matcher: Matcher, bot: Bot, event: PrivateMessageEvent):
    if str(event.user_id) not in get_driver().config.superusers:
        await matcher.finish("你不是超管，不能用这个命令")
        return

    msg = event.get_plaintext().strip()
    
    if msg.startswith("/同步"):
        msg = msg[3:].strip()
    elif msg.startswith("同步"):
        msg = msg[2:].strip()
        
    parts = msg.split()
    if len(parts) < 3:
        await matcher.finish("格式错误！\n请发送：/同步 [源ID] [目标ID] [关键词]")
        return
        
    raw_source = parts[0]
    raw_target = parts[1]
    keyword = " ".join(parts[2:]).strip()

    result = MemeManager.sync_memes(raw_source, raw_target, keyword)
    await matcher.finish(result)

async def handle_list_memes(matcher: Matcher, bot: Bot, event: MessageEvent):
    context_id = get_context_id(event)
    memes = MemeManager.get_all_memes(context_id)
    
    if not memes:
        await matcher.finish("当前群没有任何图库")
        return

    # Construct Forward Message
    msgs = []
    
    # Header node
    # Use bot's own ID and name for the node to validity
    # Or just use a fixed valid integer ID. "10000" is usually safe fake ID.
    sender_id = str(event.user_id)
    sender_name = event.sender.nickname or "Bot"
    
    msgs.append(
        MessageSegment.node_custom(
            user_id=sender_id, # Use sender's ID to look like they sent it, or bot's ID
            nickname=sender_name,
            content=Message(f"当前群共有 {len(memes)} 个图库")
        )
    )
    
    chunk_size = 50
    for i in range(0, len(memes), chunk_size):
        chunk = memes[i:i + chunk_size]
        text = "\n".join(chunk)
        msgs.append(
            MessageSegment.node_custom(
                user_id=sender_id,
                nickname=sender_name,
                content=Message(text)
            )
        )
        
    try:
        if isinstance(event, PrivateMessageEvent):
             # Private forward message
             await bot.send_private_forward_msg(user_id=event.user_id, messages=msgs)
        else:
             # Group message - use send_group_forward_msg API for better compatibility
             # Note: messages argument in onebot v11 adapter expects list of nodes
             await bot.send_group_forward_msg(group_id=event.group_id, messages=msgs)
             
    except Exception as e:
        # Avoid catching FinishedException if it somehow occurs
        from nonebot.exception import FinishedException
        if isinstance(e, FinishedException):
            raise e
            
        import traceback
        traceback.print_exc()
        await matcher.finish(f"发送合并消息失败：{e}\n请检查Bot是否有发送合并消息的权限。")

async def handle_help(matcher: Matcher):
    help_msg = (
        "✨花活列表✨\n"
        "1. 来只/来个[关键词]\n"
        "   👉 获取表情包，例如：来只哆啦A梦、来个猫猫\n"
        "2. 添加[关键词] [图片/文字]\n"
        "   👉 回复图片或文字发送：添加哆啦A梦\n"
        "   💡 添加 --force 跳过查重：添加哆啦A梦 --force\n"
        "3. 删除[关键词] [图片/文字]\n"
        "   👉 回复我发的消息发送：删除哆啦A梦\n"
        "4. 添加别名 [原名] [别名]\n"
        "   👉 例如：添加别名 哆啦A梦 蓝胖子\n"
        "5. 删除别名 [别名]\n"
        "   👉 例如：删除别名 蓝胖子\n"
        "6. 查看别名 [关键词]\n"
        "   👉 例如：查看别名 哆啦A梦\n"
        "7. 查看图库\n"
        "   👉 查看本群所有表情包库名\n\n"
        "⚠️ 注意：同步功能仅限超管使用"
    )
    await matcher.finish(help_msg)
