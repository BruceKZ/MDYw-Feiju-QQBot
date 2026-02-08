import httpx
from typing import Optional
from .models import VideoInfo, Comment

# Simple in-memory cache
# { 'bv...': (timestamp, VideoInfo) }
_VIDEO_CACHE = {}
_COMMENT_CACHE = {}
CACHE_TTL = 300  # 5 minutes

async def get_video_info(bvid: str) -> Optional[VideoInfo]:
    """
    Fetch video metadata from Bilibili API.
    """
    url = "https://api.bilibili.com/x/web-interface/view"
    params = {"bvid": bvid}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=10.0)
            data = resp.json()
            
            if data['code'] != 0:
                print(f"API Error: {data['message']}")
                return None
            
            info = data['data']
            video_info = VideoInfo(
                aid=info['aid'],
                bvid=info['bvid'],
                cid=info['cid'],
                title=info['title'],
                pic=info['pic'],
                desc=info['desc'],
                owner_name=info['owner']['name'],
                view_count=info['stat']['view'],
                date=info['pubdate'],
                url=f"https://www.bilibili.com/video/{info['bvid']}"
            )
            return video_info

    except Exception as e:
        print(f"Network/Parse Error: {e}")
        return None

async def get_top_comment(aid: int) -> Optional[Comment]:
    """
    Fetch the top listed comment (hot comment).
    """
    url = "https://api.bilibili.com/x/v2/reply/main"
    params = {
        "type": 1,  # Video type
        "oid": aid,
        "mode": 3   # Hot sort
    }
     
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=10.0)
            data = resp.json()
            
            if data['code'] != 0:
                # Code 12002 means comments closed/disabled
                return None
            
            replies = data['data'].get('replies')
            if not replies:
                return None
                
            top_reply = replies[0]
            comment = Comment(
                rpid=top_reply['rpid'],
                oid=top_reply['oid'],
                member_name=top_reply['member']['uname'],
                content=top_reply['content']['message'],
                like_count=top_reply['like'],
                date=top_reply['ctime']
            )
            return comment

    except Exception as e:
        print(f"Comment Fetch Error: {e}")
        return None
