# -*- coding: utf-8 -*-
"""
词云插件入口
Advanced Multilingual Group Word Cloud Plugin for Nonebot2
"""
import time
from typing import Dict

from nonebot import on_fullmatch, get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, Message
from nonebot.matcher import Matcher
from nonebot.log import logger

# Import shared_db
try:
    from ..shared_db import db as shared_db
except ImportError:
    # Fallback for dev environment or direct execution
    from src.plugins.shared_db import db as shared_db

from . import nlp_engine, renderer
from .config import COOLDOWN_SECONDS, CACHE_EXPIRE_SECONDS

# ============== 初始化 ==============

driver = get_driver()

# DB init moved to shared_db

# ============== 消息记录器 ==============

# Message recording is now handled by shared_db plugin

# ============== 词云命令 ==============

# CD 记录: {group_id: last_trigger_time}
_cooldown_cache: Dict[str, float] = {}

# 图片缓存: {cache_key: (image_bytes, expire_time)}
_image_cache: Dict[str, tuple] = {}


wordcloud_cmd = on_fullmatch(("词云", "wordcloud", "今日词云"), priority=5, block=True)


@wordcloud_cmd.handle()
async def handle_wordcloud(matcher: Matcher, event: GroupMessageEvent):
    """处理词云生成命令"""
    group_id = str(event.group_id)
    current_time = time.time()
    
    # CD 检查
    last_trigger = _cooldown_cache.get(group_id, 0)
    if current_time - last_trigger < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (current_time - last_trigger))
        await matcher.finish(f"词云生成冷却中，请等待 {remaining} 秒")
    
    # 检查缓存
    cache_key = f"wc_{group_id}_{int(current_time // 3600)}"  # 每小时刷新
    if cache_key in _image_cache:
        cached_img, expire_time = _image_cache[cache_key]
        if current_time < expire_time:
            logger.info(f"[WordCloud] Serving cached image for group {group_id}")
            await matcher.finish(MessageSegment.image(cached_img))
    
    # 获取消息 (fetch from shared_db)
    raw_messages = shared_db.get_messages_last_24h(group_id)
    
    if not raw_messages:
        await matcher.finish("过去24小时群里还没有足够的消息，生成不了词云！")
    
    import json

    # Filter messages (convert raw to text, filter commands/short msg)
    valid_texts = []
    for raw_msg in raw_messages:
        try:
            # Try to parse as JSON (new format)
            try:
                segments = json.loads(raw_msg)
                msg_obj = Message([MessageSegment(type=s['type'], data=s['data']) for s in segments])
            except (json.JSONDecodeError, TypeError, KeyError):
                # Fallback to string (old format)
                msg_obj = Message(raw_msg)

            # Extract plain text from raw CQ string
            txt = msg_obj.extract_plain_text().strip()
            
            # Skip empty
            if not txt:
                continue
            
            # Skip commands
            if txt.startswith(("/", "!", "！", "。", "#")):
                continue
            
            # Skip short messages
            if len(txt) < 2:
                continue
            
            valid_texts.append(txt)
        except Exception:
            continue

    if len(valid_texts) < 10:
        await matcher.finish(f"消息太少了（仅{len(valid_texts)}条），再聊一会儿再来吧！")

    # 分词处理
    try:
        word_freq = nlp_engine.tokenize_texts(valid_texts)
    except Exception as e:
        logger.error(f"[WordCloud] Tokenization failed: {e}")
        await matcher.finish("分词处理失败，请稍后重试")
    
    if not word_freq or len(word_freq) < 5:
        await matcher.finish("有效词汇太少，生成不了词云！")
    
    # 生成图片
    try:
        img_bytes = renderer.generate_wordcloud(word_freq, use_mask=True)
        
        # 如果带蒙版失败，尝试简单模式
        if not img_bytes:
            img_bytes = renderer.generate_wordcloud_simple(word_freq)
        
    except Exception as e:
        logger.error(f"[WordCloud] Rendering failed: {e}")
        await matcher.finish("词云生成失败，请稍后重试")
    
    if not img_bytes:
        await matcher.finish("图片生成失败，可能是系统资源不足")
    
    # 更新缓存和CD
    _cooldown_cache[group_id] = current_time
    _image_cache[cache_key] = (img_bytes, current_time + CACHE_EXPIRE_SECONDS)
    
    # 清理过期缓存
    expired_keys = [k for k, (_, exp) in _image_cache.items() if current_time > exp]
    for k in expired_keys:
        del _image_cache[k]
    
    logger.info(f"[WordCloud] Generated for group {group_id}, words: {len(word_freq)}, messages: {len(valid_texts)}")
    
    await matcher.finish(MessageSegment.image(img_bytes))
