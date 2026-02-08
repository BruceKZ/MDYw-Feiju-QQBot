from typing import Optional
from pydantic import BaseModel

class VideoInfo(BaseModel):
    aid: int
    bvid: str
    cid: int
    title: str
    pic: str  # Cover image URL
    desc: str
    owner_name: str
    view_count: int
    date: int # Pubdate
    url: str  # Clean video URL

class Comment(BaseModel):
    rpid: int
    oid: int
    member_name: str
    content: str
    like_count: int
    date: int
