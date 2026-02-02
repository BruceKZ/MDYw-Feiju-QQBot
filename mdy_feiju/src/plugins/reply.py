from nonebot import on_regex
from nonebot.adapters.onebot.v11 import Bot, Event

bad_word = on_regex(r"臭婊子", priority=10, block=True)
@bad_word.handle()
async def _(bot: Bot, event: Event):
    text = event.get_plaintext()
    await bad_word.finish(text.replace("臭婊子", "好女孩"))


good_girl = on_regex(r"好女孩", priority=10, block=True)


@good_girl.handle()
async def _(bot: Bot, event: Event):
    text = event.get_plaintext()
    await good_girl.finish(text.replace("好女孩", "臭婊子"))

s1 = on_regex(r"好婊子", priority=10, block=True)
@s1.handle()
async def _(bot: Bot, event: Event):
    text = event.get_plaintext()
    await s1.finish(text.replace("好婊子", "臭女孩")) 


s2 = on_regex(r"臭女孩", priority=10, block=True)
@s2.handle()
async def _(bot: Bot, event: Event):
    text = event.get_plaintext()
    await s2.finish(text.replace("臭女孩", "好婊子"))           
    