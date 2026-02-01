import httpx
from io import BytesIO
from PIL import Image
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, MessageEvent
from nonebot.log import logger

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
            
        # If no resize needed, return original data
        return img_data
            
    except Exception as e:
        logger.error(f"Failed to resize image: {e}")
    return img_data

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

async def download_url(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content
