import re
import httpx
import imagehash
from io import BytesIO
from pathlib import Path
from PIL import Image
from nonebot import on_regex, on_message, on_startswith, get_driver, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment, GroupMessageEvent, MessageEvent, PrivateMessageEvent
from nonebot.log import logger

from .db import (
    init_db, get_category_id, create_category, add_image, 
    get_random_image, check_duplicate, delete_image_by_hash,
    migrate_lowercase_categories, resize_existing_images, get_all_images
)

MAX_DIMENSION = 512

def resize_image(img_data: bytes) -> bytes:
    """
    Resize image if dimensions exceed MAX_DIMENSION.
    Preserves format (GIF, PNG, JPEG).
    """
    try:
        img = Image.open(BytesIO(img_data))
        format = img.format or "PNG"
        w, h = img.size
        
        if max(w, h) > MAX_DIMENSION:
            # Calculate new size
            ratio = MAX_DIMENSION / max(w, h)
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
                
            return buf.getvalue()
            
        # If no resize needed, return original data but ensure we can read it
        # Actually, let's just return original data if it's small enough
        return img_data
            
    except Exception as e:
        logger.error(f"Failed to resize image: {e}")
    return img_data

# Initialize DB on startup
driver = get_driver()

@driver.on_startup
async def _():
    init_db()
    migrate_lowercase_categories()
    resize_existing_images(MAX_DIMENSION)


def get_context_id(event: MessageEvent) -> str:
    """
    Get a unique context ID for the event.
    For GroupMessageEvent, returns group_id.
    For PrivateMessageEvent, returns 'private_{user_id}'.
    """
    if isinstance(event, GroupMessageEvent):
        return str(event.group_id)
    elif isinstance(event, PrivateMessageEvent):
        return f"private_{event.user_id}"
    else:
        # Fallback for other types if any
        return f"unknown_{event.user_id}"

# --- Command Handlers ---

# 1. Get Meme: "来只xxx"
# Regex to capture "来只" followed by anything
get_meme_cmd = on_regex(r"^来只(.+)$", priority=99, block=False)

@get_meme_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    # Extract category name
    match = re.match(r"^来只(.+)$", event.get_plaintext().strip())
    if not match:
        return
    
    raw_text = match.group(1).strip()
    context_id = get_context_id(event)
    
    # Prefix Maximum Matching
    found_cat_id = None
    matched_name = ""
    
    # Loop from full length down to 1
    for i in range(len(raw_text), 0, -1):
        potential_name = raw_text[:i].strip()
        if not potential_name:
            continue
            
        # Try to find in current group (use lowercase)
        cat_id = get_category_id(potential_name.lower(), context_id)
        
        if cat_id:
            found_cat_id = cat_id
            matched_name = potential_name
            break
            
    if not found_cat_id:
        await get_meme_cmd.send(f"一张{raw_text}都没有，来鸡毛？")
        return

    img_data = get_random_image(found_cat_id)
    if not img_data:
        await get_meme_cmd.send(f"一张{raw_text}都没有，来鸡毛？")
        return
        
    await get_meme_cmd.send(MessageSegment.image(img_data))


# 2. Add Meme: "添加xxx"
add_meme_cmd = on_message(priority=10, block=False)

@add_meme_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    msg = event.get_plaintext().strip()
    
    # Check if message starts with "添加"
    if not msg.startswith("添加"):
        return
        
    category_name = msg[2:].strip()
    if not category_name:
        return

    if not event.reply:
        return

    # Check if the replied message has an image
    reply_msg = event.reply.message
    images = [seg for seg in reply_msg if seg.type == "image"]
    
    if not images:
        return

    img_url = images[0].data.get("url")
    if not img_url:
        return

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(img_url)
            resp.raise_for_status()
            raw_img_data = resp.content
            
        # Resize image (handles GIFs and preserves format)
        final_img_data = resize_image(raw_img_data)
        
        # Calculate hash for duplicate check
        # Note: imagehash might not work well with animated GIFs directly, 
        # usually it takes the first frame.
        check_img = Image.open(BytesIO(final_img_data))
        new_hash = str(imagehash.phash(check_img))
        
        context_id = get_context_id(event)
        
        # Get or Create Category for THIS group (use lowercase)
        cat_id = get_category_id(category_name.lower(), context_id)
        if not cat_id:
            cat_id = create_category(category_name.lower(), context_id)
            
        # Check duplicates in THIS category
        if check_duplicate(cat_id, new_hash):
            await add_meme_cmd.send("水过了！你老冯的")
            return
        
        add_image(cat_id, final_img_data, new_hash)
        await add_meme_cmd.send(f"成功添加{category_name}！")
        return

    except Exception as e:
        await add_meme_cmd.send(f"添加失败：{e}")
        return


# 3. Delete Meme: "删除xxx"
del_meme_cmd = on_startswith("删除", priority=10, block=False)

@del_meme_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    msg = event.get_plaintext().strip()
    category_name = msg[2:].strip()
    
    if not category_name:
        return

    if not event.reply:
        await del_meme_cmd.send("删哪个")
        return

    # Check if the replied message was sent by the bot
    if str(event.reply.sender.user_id) != str(bot.self_id):
        await del_meme_cmd.send("不是我发的你让我删？")
        return

    reply_msg = event.reply.message
    images = [seg for seg in reply_msg if seg.type == "image"]
    
    if not images:
        await del_meme_cmd.send("说鸡毛呢")
        return

    img_url = images[0].data.get("url")
    if not img_url:
        await del_meme_cmd.send("图寄了，不删了")
        return

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(img_url)
            resp.raise_for_status()
            target_img_data = resp.content
            
        target_img = Image.open(BytesIO(target_img_data))
        target_hash = str(imagehash.phash(target_img))

        context_id = get_context_id(event)
        
        # Try to delete from current group first (use lowercase)
        cat_id = get_category_id(category_name.lower(), context_id)
        deleted = False
        
        if cat_id:
            deleted = delete_image_by_hash(cat_id, target_hash)
            
        # If not found/deleted in group, try global (if user has permission? For now allow deleting global if it matches)
        # Wait, allowing any group to delete global images is risky. 
        # But if they see it, they might want to delete it.
        # Let's allow it for now as per "simple" logic, or restrict?
        # User said "Isolation". If I delete global, it affects everyone.
        # Maybe I should ONLY allow deleting from own group?
        # But if they got a global image, they can't delete it? That's annoying.
        # Let's try to delete from global if not found in group.
        # If not found/deleted in group, do NOT try global. Strict isolation.
        # if not deleted:
        #     global_cat_id = get_category_id(category_name, "global")
        #     if global_cat_id:
        #         deleted = delete_image_by_hash(global_cat_id, target_hash)

        if deleted:
            await del_meme_cmd.send(f"已删除！{category_name}House")
            return
        else:
            await del_meme_cmd.send(f"{category_name}已经被爱死了...")
            return

    except Exception as e:
        await del_meme_cmd.send(f"删除失败：{e}，{category_name}别走😭")
        return

# 4. Sync Meme: "/sync source_group target_group keyword" (Superuser & Private only)
# Supports 'p' prefix for private chat (e.g., p12345)
sync_cmd = on_command("同步", priority=5, block=True)

@sync_cmd.handle()
async def _(bot: Bot, event: PrivateMessageEvent):
    # Check Superuser
    if str(event.user_id) not in get_driver().config.superusers:
        await sync_cmd.finish("你不是超管，不能用这个命令")
        return

    # Get arguments
    # remove the command itself
    msg = event.get_plaintext().strip()
    # Handle cases where command might be "/同步" or "同步"
    if msg.startswith("/同步"):
        msg = msg[3:].strip()
    elif msg.startswith("同步"):
        msg = msg[2:].strip()
        
    parts = msg.split()
    if len(parts) < 3:
        await sync_cmd.finish("格式错误！\n请发送：/同步 [源ID] [目标ID] [关键词]")
        return
        
    raw_source = parts[0]
    raw_target = parts[1]
    # The rest is the keyword
    keyword = " ".join(parts[2:]).strip()

    def parse_context(raw: str) -> str:
        if raw.lower().startswith('p'):
            return f"private_{raw[1:]}"
        return raw

    source_group = parse_context(raw_source)
    target_group = parse_context(raw_target)
    
    # 1. Check Source Category
    source_cat_id = get_category_id(keyword.lower(), source_group)
    if not source_cat_id:
        await sync_cmd.finish(f"源 ({source_group}) 没有关于 '{keyword}' 的图片。")
        
    # 2. Get Source Images
    images = get_all_images(source_cat_id)
    if not images:
        await sync_cmd.finish(f"源 ({source_group}) 的 '{keyword}' 是空的。")
        
    # 3. Get/Create Target Category
    target_cat_id = get_category_id(keyword.lower(), target_group)
    if not target_cat_id:
        target_cat_id = create_category(keyword.lower(), target_group)
        
    # 4. Sync
    count = 0
    skipped = 0
    
    for img_data, img_phash in images:
        if check_duplicate(target_cat_id, img_phash):
            skipped += 1
            continue
            
        add_image(target_cat_id, img_data, img_phash)
        count += 1
        
    await sync_cmd.finish(f"同步完成！\n关键字: {keyword}\n成功同步: {count} 张\n跳过重复: {skipped} 张")
