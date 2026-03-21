import time
import logging
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from .ntp_time import get_totp_code, get_accurate_datetime_shanghai

logger = logging.getLogger(__name__)

# Rate limiting: user_id -> last request timestamp
_rate_limit: dict[str, float] = {}
_RATE_LIMIT_SECONDS = 10

from .db import (
    init_db,
    add_secret,
    delete_secret,
    get_secret,
    grant_permission,
    revoke_permission,
    set_alias,
    set_note,
    clear_note,
    get_note,
    resolve_secret_name,
    get_all_user_secrets
)

__plugin_meta__ = PluginMetadata(
    name="2FA Plugin",
    description="Personal 2FA Code Generator with Sharing",
    usage="Send /2fa_help for details.",
)

# Initialize DB on load
init_db()

# Commands
cmd_help = on_command("2fa_help", priority=10, block=True)
cmd_help_full = on_command("2fa_help_full", aliases={"2fahelpfull"}, priority=10, block=True)
cmd_add = on_command("2fa_add", priority=10, block=True)
cmd_del = on_command("2fa_del", priority=10, block=True)
cmd_grant = on_command("2fa_grant", priority=10, block=True)
cmd_revoke = on_command("2fa_revoke", priority=10, block=True)
cmd_alias = on_command("2fa_alias", priority=10, block=True)
cmd_list = on_command("2fa_list", priority=10, block=True)
cmd_note = on_command("2fa_note", priority=10, block=True)
cmd_note_del = on_command("2fa_note_del", priority=10, block=True)
cmd_note_get = on_command("2fa_note_get", priority=10, block=True)
cmd_get = on_command("2fa", priority=10, block=True)

@cmd_help.handle()
async def handle_help(event: PrivateMessageEvent):
    help_text = (
        "2FA Commands:\n"
        "/2fa_add [Name] [URL] [Secret]\n"
        "/2fa_del [Name] (Creator deletes, others self-revoke)\n"
        "/2fa_grant [Name] [QQ]\n"
        "/2fa_revoke [Name] [QQ]\n"
        "/2fa_alias [Name] [Alias]\n"
        "/2fa_note [Name] [Note]\n"
        "/2fa_note_del [Name]\n"
        "/2fa_note_get [Name]\n"
        "/2fa_list\n"
        "/2fa [Name]\n"
        "(Send /2fa_help_full for detailed explanation in Chinese)"
    )
    await cmd_help.finish(help_text)

@cmd_help_full.handle()
async def handle_help_full(event: PrivateMessageEvent):
    help_text = (
        "【2FA 完整功能指南】\n"
        "本插件支持“私有密钥库”与“好友共享”功能。\n\n"
        "1. 基本操作：\n"
        " /2fa_add [名称] [说明] [Secret]\n"
        "   - 添加后你是该密钥的最高权限创建者\n"
        " /2fa_list\n"
        "   - 查看你创建的以及别人分享给你的所有密钥\n"
        " /2fa [名称/自动补充的别名]\n"
        "   - 无论你是创建者还是被授权者，输入短名称即可获取验证码\n\n"
        "2. 权限管理 (仅创建者)：\n"
        " /2fa_grant [名称] [目标QQ]\n"
        "   - 将该密钥使用权分享给某个QQ号\n"
        " /2fa_revoke [名称] [目标QQ]\n"
        "   - 收回某人对该密钥的使用权\n\n"
        "3. 个性化设置 (专属你自己，别人看不见)：\n"
        " /2fa_alias [别人分享给你的名称] [你的专属别名]\n"
        "   - 为别人发给你的长密钥起个好记的短别名\n"
        " /2fa_note [名称] [备注内容]\n"
        "   - 给你列表里的任何一个密钥加备忘录\n"
        " /2fa_note_get / /2fa_note_del\n"
        "   - 单独查看或清除该专属备注\n\n"
        "4. 删除操作：\n"
        " /2fa_del [名称]\n"
        "   - 如果是你创建的，则全网彻底销毁；如果是别人分享给你的，则是你单方面“退订/拒收”"
    )
    await cmd_help_full.finish(help_text)

@cmd_add.handle()
async def handle_add(event: PrivateMessageEvent, args: Message = CommandArg()):
    content = args.extract_plain_text().strip().split(maxsplit=2)
    if len(content) < 3:
        await cmd_add.finish("Usage: /2fa_add [Name] [URL/Info] [Secret]")
    
    user_id = event.get_user_id()
    name = content[0].upper()
    url = content[1]
    secret = content[2]
    
    secret = secret.replace(" ", "")

    if not secret.isalnum():
        await cmd_add.finish("Error: Secret contains invalid characters!")
        
    full_name = f"{user_id}_{name}"
    add_secret(full_name, url, secret, user_id)
    await cmd_add.finish(f"Added: {name}")

@cmd_del.handle()
async def handle_del(event: PrivateMessageEvent, args: Message = CommandArg()):
    name = args.extract_plain_text().strip().upper()
    if not name:
        await cmd_del.finish("Usage: /2fa_del [Name]")
    
    user_id = event.get_user_id()
    resolved_name = resolve_secret_name(user_id, name)
    if not resolved_name:
        await cmd_del.finish(f"Failed: {name} not found.")
        
    if delete_secret(resolved_name, user_id):
        display_name = resolved_name.removeprefix(f"{user_id}_")
        await cmd_del.finish(f"Deleted/Revoked: {display_name}")
    else:
        display_name = resolved_name.removeprefix(f"{user_id}_")
        await cmd_del.finish(f"Failed: Could not delete {display_name}.")

@cmd_grant.handle()
async def handle_grant(event: PrivateMessageEvent, args: Message = CommandArg()):
    content = args.extract_plain_text().strip().split()
    if len(content) < 2:
        await cmd_grant.finish("Usage: /2fa_grant [Name] [Target_QQ]")
    
    user_id = event.get_user_id()
    name = content[0].upper()
    target_qq = content[1]
    
    resolved_name = resolve_secret_name(user_id, name)
    if not resolved_name:
        await cmd_grant.finish(f"Failed: {name} not found.")
        
    msg = grant_permission(resolved_name, user_id, target_qq)
    await cmd_grant.finish(msg)

@cmd_revoke.handle()
async def handle_revoke(event: PrivateMessageEvent, args: Message = CommandArg()):
    content = args.extract_plain_text().strip().split()
    if len(content) < 2:
        await cmd_revoke.finish("Usage: /2fa_revoke [Name] [Target_QQ]")
    
    user_id = event.get_user_id()
    name = content[0].upper()
    target_qq = content[1]
    
    resolved_name = resolve_secret_name(user_id, name)
    if not resolved_name:
        await cmd_revoke.finish(f"Failed: {name} not found.")
        
    msg = revoke_permission(resolved_name, user_id, target_qq)
    await cmd_revoke.finish(msg)

@cmd_alias.handle()
async def handle_alias(event: PrivateMessageEvent, args: Message = CommandArg()):
    content = args.extract_plain_text().strip().split()
    if len(content) < 2:
        await cmd_alias.finish("Usage: /2fa_alias [Name] [Alias]")
    
    user_id = event.get_user_id()
    name = content[0].upper()
    alias = content[1].upper()
    
    resolved_name = resolve_secret_name(user_id, name)
    if not resolved_name:
        await cmd_alias.finish(f"Failed: {name} not found.")
        
    msg = set_alias(resolved_name, user_id, alias)
    await cmd_alias.finish(msg)

@cmd_list.handle()
async def handle_list(event: PrivateMessageEvent):
    user_id = event.get_user_id()
    msg = get_all_user_secrets(user_id)
    await cmd_list.finish(msg)

@cmd_note.handle()
async def handle_note(event: PrivateMessageEvent, args: Message = CommandArg()):
    content = args.extract_plain_text().strip().split(maxsplit=1)
    if len(content) < 2:
        await cmd_note.finish("Usage: /2fa_note [Name] [Note]")
    
    user_id = event.get_user_id()
    name = content[0].upper()
    note = content[1]
    
    resolved_name = resolve_secret_name(user_id, name)
    if not resolved_name:
        await cmd_note.finish(f"Failed: {name} not found.")
        
    msg = set_note(resolved_name, user_id, note)
    await cmd_note.finish(msg)

@cmd_note_del.handle()
async def handle_note_del(event: PrivateMessageEvent, args: Message = CommandArg()):
    name = args.extract_plain_text().strip().upper()
    if not name:
        await cmd_note_del.finish("Usage: /2fa_note_del [Name]")
    
    user_id = event.get_user_id()
    resolved_name = resolve_secret_name(user_id, name)
    if not resolved_name:
        await cmd_note_del.finish(f"Failed: {name} not found.")
        
    msg = clear_note(resolved_name, user_id)
    await cmd_note_del.finish(msg)

@cmd_note_get.handle()
async def handle_note_get(event: PrivateMessageEvent, args: Message = CommandArg()):
    name = args.extract_plain_text().strip().upper()
    if not name:
        await cmd_note_get.finish("Usage: /2fa_note_get [Name]")
    
    user_id = event.get_user_id()
    resolved_name = resolve_secret_name(user_id, name)
    if not resolved_name:
        await cmd_note_get.finish(f"Failed: {name} not found.")
        
    msg = get_note(resolved_name, user_id)
    await cmd_note_get.finish(msg)

@cmd_get.handle()
async def handle_get(event: PrivateMessageEvent, args: Message = CommandArg()):
    user_id = event.get_user_id()
    query = args.extract_plain_text().strip().upper()
    if not query:
        return

    # Rate limiting
    now = time.time()
    last = _rate_limit.get(user_id, 0.0)
    if now - last < _RATE_LIMIT_SECONDS:
        remaining_wait = int(_RATE_LIMIT_SECONDS - (now - last))
        await cmd_get.finish(f"请求过于频繁，请 {remaining_wait} 秒后再试。")
    _rate_limit[user_id] = now

    resolved_name = resolve_secret_name(user_id, query)
    if not resolved_name:
        await cmd_get.finish(f"Not found: {query} (Check /2fa_list)")

    secret = get_secret(resolved_name, user_id)
    if not secret:
        await cmd_get.finish("Error: Secret not accessible.")

    try:
        code, remaining = get_totp_code(secret)
    except Exception:
        logger.exception("Failed to generate TOTP code for %s", resolved_name)
        await cmd_get.finish("生成验证码失败，请稍后再试。")

    now_gmt8 = get_accurate_datetime_shanghai().strftime("%Y-%m-%d %H:%M:%S")
    display_name = resolved_name.removeprefix(f"{user_id}_")
    await cmd_get.send(f"[{now_gmt8}]\n{display_name}: {code}\nRemaining time: {remaining}s")
    await cmd_get.finish(code)
