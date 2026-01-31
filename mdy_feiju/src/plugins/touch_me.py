import httpx
from io import BytesIO
from PIL import Image
from nonebot import on_regex
from nonebot.adapters.onebot.v11 import MessageSegment, MessageEvent


pet = on_regex(r"^摸\s*", priority=1, block=True)

@pet.handle()
async def handle_pet(event: MessageEvent):
    user_id = None
    for seg in event.get_message():
        if seg.type == "at":
            user_id = seg.data["qq"]
            break
    
    if not user_id:
        return

    avatar_url = f"http://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(avatar_url)
            if resp.status_code != 200:
                await pet.finish("哥们你头像呢...")
            
            avatar_img = Image.open(BytesIO(resp.content)).convert("RGBA")

            size = (200, 200)
            avatar_img = avatar_img.resize(size)
            avatar_img = avatar_img.rotate(180)
            
            output = BytesIO()
            avatar_img.save(output, format="PNG")
            
            await pet.finish(MessageSegment.image(output.getvalue()))
            
    except Exception as e:
        from nonebot.exception import FinishedException
        if isinstance(e, FinishedException):
            raise e
        await pet.finish(f"没摸到：{str(e)}")