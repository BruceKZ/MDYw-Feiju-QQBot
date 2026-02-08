import json
from nonebot import on_regex, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.plugin import PluginMetadata
from nonebot.typing import T_State

from .extractor import extract_bv, extract_from_json, BV_PATTERN
from .data_source import get_video_info
from .render import render_card_response, render_text_summary

__plugin_meta__ = PluginMetadata(
    name="Bilibili Link/Card Converter",
    description="Video link to card & Card to text summary",
    usage="Send Bilibili video link or share card",
)

# 1. Text/Link -> Card
# Match any message containing "BV" or "b23.tv"
# We use a broad regex or a priority handler
bilibili_link = on_regex(
    r"(BV[a-zA-Z0-9]{10}|b23\.tv/[a-zA-Z0-9]+|bilibili\.com/video/BV)",
    priority=10,
    block=False # Don't block other plugins if user just mentions it
)

@bilibili_link.handle()
async def handle_link(bot: Bot, event: GroupMessageEvent, state: T_State):
    text = event.get_plaintext()
    bv_id = await extract_bv(text)
    
    if not bv_id:
        return

    # Fetch data
    video = await get_video_info(bv_id)
    if not video:
        # Silently fail or simple log, don't spam if invalid
        return
        
    # Construct response
    msg = render_card_response(video)
    await bilibili_link.finish(msg)


# 2. Card -> Text
# Update: Handle JSON/XML cards
# This is trickier as Nonebot regex might not trigger on JSON card type messages depending on adapter settings
# We use on_message with a rule
async def is_json_or_xml_card(event: GroupMessageEvent) -> bool:
    # Check if message contains JSON or XML segment
    for seg in event.message:
        if seg.type in ('json', 'xml'):
            return True
    return False

bilibili_card = on_message(rule=is_json_or_xml_card, priority=10, block=False)

@bilibili_card.handle()
async def handle_card(bot: Bot, event: GroupMessageEvent):
    for seg in event.message:
        if seg.type == 'json':
            try:
                raw_data = seg.data.get('data', '{}')
                if isinstance(raw_data, dict):
                    data = raw_data
                else:
                    data = json.loads(raw_data)
                
                # Step 1: Extract URL from JSON
                raw_url = extract_from_json(data)
                
                if raw_url:
                    # Step 2: Resolve BV from the URL (handles short links too)
                    bv_id = await extract_bv(raw_url)
                    
                    if bv_id:
                        await _process_card_bv(bv_id, bot, event)
                        return # Process first valid card only
            except Exception:
                continue
        
        elif seg.type == 'xml':
            pass

async def _process_card_bv(bv_id: str, bot: Bot, event: GroupMessageEvent):
    video = await get_video_info(bv_id)
    if not video:
        return
        
    summary = render_text_summary(video)
    
    # Reply with text summary
    await bilibili_card.finish(summary)
