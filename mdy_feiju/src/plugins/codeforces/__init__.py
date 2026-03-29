import re
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageSegment, MessageEvent, Bot
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.adapters import Message
from nonebot.exception import FinishedException
from nonebot import logger

from .api import fetch_user_info, get_percentile, update_cache, get_cache_time
from .draw import draw_cf_card

cf_cmd = on_command("cf", aliases={"codeforces"}, priority=5, block=True)
cf_update_cmd = on_command("cf_update_rating", priority=5, block=True)

@cf_update_cmd.handle()
async def handle_update(bot: Bot, event: MessageEvent):
    await cf_update_cmd.send("⏳ 正在扫描最近6个月所有比赛的 Rating 数据，请耐心等待...")
    ts = await update_cache()
    if ts:
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        await cf_update_cmd.finish(f"✅ CF Rating 榜单已更新完毕。\n最后更新时间: {ts_str} (UTC+8)")
    else:
        await cf_update_cmd.finish("❌ 更新失败，请检查网络或稍后重试。")

@cf_cmd.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    txt = arg.extract_plain_text().strip()
    if not txt:
        await cf_cmd.finish("用法: /cf <Codeforces_ID>")
        
    handle = txt
    user_info = await fetch_user_info(handle)
    if not user_info:
        await cf_cmd.finish(f"未找到用户 {handle}，请检查 ID 是否拼写正确。")
        
    # Percentile: purely from local cache
    rating = user_info.get("rating", 0)
    percent = None
    if rating > 0:
        percent = get_percentile(rating)
    
    # Get the cache data timestamp for the card watermark
    cache_time = get_cache_time()
        
    try:
        img_bytes = await draw_cf_card(user_info, percent, cache_time)
        await cf_cmd.finish(MessageSegment.image(img_bytes))
    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"Error drawing CF card: {e}")
        await cf_cmd.finish(f"生成卡片时出错: {e}")
