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

s1 = on_fullmatch("好婊子", priority=10, block=True)
@s1.handle()
async def _(bot: Bot, event: Event):
    await s1.finish("臭女孩") 


s2 = on_fullmatch("臭女孩", priority=10, block=True)
@s2.handle()
async def _(bot: Bot, event: Event):
    await s2.finish("好婊子")           
    