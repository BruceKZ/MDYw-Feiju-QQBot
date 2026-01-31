from nonebot import on_startswith
from nonebot.adapters.onebot.v11 import Bot, Event

# === 场景：检测以 "我爱你" 开头的消息 ===
# 触发示例：
# 用户：我爱你
# 用户：我爱你啊机器人
# 用户：我爱你 (无需 @，无需 /)
love = on_startswith("我爱你", priority=10, block=True)


@love.handle()
async def _(bot: Bot, event: Event):
    # 发送回复
    await love.finish("我也爱你捏！(脸红)")


# # === 场景：检测前缀指令，比如 "搜索 xxx" ===
# # 触发示例：用户发 "搜索 哆啦A梦"
# search = on_startswith("搜索")
#
#
# @search.handle()
# async def _(bot: Bot, event: Event):
#     # 获取完整的消息文本
#     text = event.get_plaintext()
#     # 去掉开头的 "搜索" 两个字，剩下的就是关键词
#     # strip() 是为了去掉可能存在的空格
#     keyword = text.replace("搜索", "", 1).strip()
#
#     if not keyword:
#         await search.finish("你要搜什么呀？请发送：搜索 关键词")
#
#     await search.finish(f"正在为你搜索【{keyword}】... (假装在搜)")