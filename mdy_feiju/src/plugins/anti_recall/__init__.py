from nonebot import on_command, on_notice, get_driver
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupRecallNoticeEvent,
    Message,
    MessageSegment,
)
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg
from nonebot.log import logger

# Import shared_db
try:
    from ..shared_db import db
except ImportError:
    from src.plugins.shared_db import db

# 1. Command to enable/disable anti-recall for a user
# Only superusers can use this command
monitor_cmd = on_command("锁住", aliases={"开启防撤回"}, permission=SUPERUSER, priority=10, block=True)
unmonitor_cmd = on_command("放过", aliases={"关闭防撤回"}, permission=SUPERUSER, priority=10, block=True)

@monitor_cmd.handle()
async def handle_monitor(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """
    Enable anti-recall for mentioned users.
    Usage: /防撤回 @user
    """
    # Get mentioned users from the message
    segments = event.message
    mentioned_users = [seg.data["qq"] for seg in segments if seg.type == "at"]
    
    if not mentioned_users:
        await monitor_cmd.finish("请@想要开启防撤回的用户！")

    group_id = str(event.group_id)
    added_users = []
    
    for user_id in mentioned_users:
        user_id = str(user_id)
        # Avoid monitoring the bot itself if accidentally at-ed
        if user_id == str(event.self_id):
            continue
            
        try:
            db.add_monitor(group_id, user_id)
            added_users.append(user_id)
        except Exception as e:
            logger.error(f"[AntiRecall] Failed to add monitor for {user_id}: {e}")

    if added_users:
        await monitor_cmd.finish(f"已开启对 {len(added_users)} 名用户的防撤回监控！")
    else:
        await monitor_cmd.finish("未能添加监控，可能是因为只@了机器人自己。")


@unmonitor_cmd.handle()
async def handle_unmonitor(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """
    Disable anti-recall for mentioned users.
    Usage: /关闭防撤回 @user
    """
    segments = event.message
    mentioned_users = [seg.data["qq"] for seg in segments if seg.type == "at"]

    if not mentioned_users:
        await unmonitor_cmd.finish("请@想要关闭防撤回的用户！")

    group_id = str(event.group_id)
    removed_users = []

    for user_id in mentioned_users:
        user_id = str(user_id)
        try:
            db.remove_monitor(group_id, user_id)
            removed_users.append(user_id)
        except Exception as e:
            logger.error(f"[AntiRecall] Failed to remove monitor for {user_id}: {e}")

    if removed_users:
        await unmonitor_cmd.finish(f"已关闭对 {len(removed_users)} 名用户的防撤回监控！")
    else:
        await unmonitor_cmd.finish("未能移除监控。")


# 3. List monitored users
# Everyone can use this
list_monitor_cmd = on_command("查看锁住名单", aliases={"查看监控名单", "监控列表"}, priority=10, block=True)

@list_monitor_cmd.handle()
async def handle_list_monitored(bot: Bot, event: GroupMessageEvent):
    """
    List all monitored users in the group.
    Format: @User 123456
    """
    group_id = str(event.group_id)
    monitored_users = db.get_monitored_users(group_id)
    
    if not monitored_users:
        await list_monitor_cmd.finish("当前群内没有被监控的用户。")
        
    msg = Message()
    for user_id in monitored_users:
        msg += MessageSegment.at(user_id) + Message(f" {user_id}\n")
        
    await list_monitor_cmd.finish(msg)


# 2. Handle group recall events
recall_matcher = on_notice(priority=5, block=False)

@recall_matcher.handle()
async def handle_recall(bot: Bot, event: GroupRecallNoticeEvent):
    """
    Listen for group recall events.
    If the user is monitored, resend the message.
    """
    group_id = str(event.group_id)
    operator_id = str(event.operator_id) # Who executed the recall
    user_id = str(event.user_id)         # Who sent the original message
    message_id = str(event.message_id)   # The recalled message ID

    # Check if the user is monitored in this group
    if not db.is_monitored(group_id, user_id):
        return

    # If the operator is an admin/owner recalling someone else's message, we probably shouldn't interfere?
    # Or maybe we should? The requirement says "If A recalls a message...".
    # Usually, if A recalls their own message, operator_id == user_id.
    # If an admin recalls A's message, operator_id != user_id.
    # The requirement specifically says "If A recalls a message", implying self-recall.
    # Let's strict it to self-recall for now to avoid annoying admins.
    if operator_id != user_id:
        return

    # Retrieve the old message content from shared_db
    try:
        msg_data = db.get_message_details(message_id)
        if not msg_data:
            logger.warning(f"[AntiRecall] Recalled message {message_id} not found in DB.")
            return
        
        # msg_data is tuple (user_id, content)
        _, content = msg_data
        
        # Construct the response
        # "A 刚刚撤回了消息，他说：\n{content}"
        
        import json
        
        # Try to parse as JSON (new format), fallback to string (old format)
        try:
            segments = json.loads(content)
            # Reconstruct Message from JSON segments
            # segments is a list of dicts, e.g. [{'type': 'text', 'data': {'text': '...'}}]
            original_message = Message([MessageSegment(type=s['type'], data=s['data']) for s in segments])
        except (json.JSONDecodeError, TypeError, KeyError):
            # Fallback for legacy messages stored as raw string
            original_message = Message(content)

        # Construct the response
        # "@user 刚刚撤回了消息，他说：\n{content}"
        prefix = MessageSegment.at(event.user_id) + Message(" 刚刚撤回了消息，他说：\n")
        response = prefix + original_message
        
        # Send it
        await bot.send_group_msg(group_id=event.group_id, message=response)
        
        logger.info(f"[AntiRecall] Resent recalled message from {user_id} in {group_id}")

    except Exception as e:
        logger.error(f"[AntiRecall] Error handling recall: {e}")
