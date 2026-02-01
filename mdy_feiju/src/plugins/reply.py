from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, Event

bad_word = on_fullmatch("臭婊子", priority=10, block=True)


@bad_word.handle()
async def _(bot: Bot, event: Event):
    await bad_word.finish("好女孩")


good_girl = on_fullmatch("好女孩", priority=10, block=True)


@good_girl.handle()
async def _(bot: Bot, event: Event):
    await good_girl.finish("臭婊子")