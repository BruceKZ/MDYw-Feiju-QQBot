from nonebot.adapters.onebot.v11 import Message, MessageSegment
from .models import VideoInfo, Comment

import datetime

def render_card_response(video: VideoInfo) -> Message:
    """
    Construct a unified response message (Image + Text).
    """
    msg = Message()
    
    # Cover image
    msg.append(MessageSegment.image(video.pic))
    
    # Unified Info Block
    # Time formatting
    dt = datetime.datetime.fromtimestamp(video.date)
    date_str = dt.strftime("%Y-%m-%d")
    
    content = (
        f"\n📺 {video.title}\n"
        f"👤 UP：{video.owner_name}  ▶️ {scale_number(video.view_count)}\n"
        f"📅 发布：{date_str}\n"
        f"🔗 {video.url}"
    )
    
    msg.append(MessageSegment.text(content))
    return msg

def render_text_summary(video: VideoInfo) -> Message:
    """
    Same as card response for now, to ensure unified experience even from card inputs.
    """
    return render_card_response(video)

def scale_number(num: int) -> str:
    if num >= 10000:
        return f"{num/10000:.1f}万"
    return str(num)
