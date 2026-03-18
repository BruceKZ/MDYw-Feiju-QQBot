
from nonebot import on_command, require
from nonebot.adapters.onebot.v11 import Message, MessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
import pyotp
from .db import (
    init_db,
    add_authorized_user,
    remove_authorized_user,
    get_authorized_users,
    add_secret,
    get_secret,
    is_authorized
)

__plugin_meta__ = PluginMetadata(
    name="2FA Plugin",
    description="2FA Code Generator for Authorized Users",
    usage="/2fa [name]",
)

# Initialize DB on load
init_db()

# Superuser Commands
cmd_add_user = on_command("2fa_add_user", permission=SUPERUSER, priority=10, block=True)
cmd_del_user = on_command("2fa_del_user", permission=SUPERUSER, priority=10, block=True)
cmd_list_users = on_command("2fa_list_users", permission=SUPERUSER, priority=10, block=True)
cmd_add_secret = on_command("2fa_add", permission=SUPERUSER, priority=10, block=True)

# User Commands
cmd_get_code = on_command("2fa", priority=10, block=True)

@cmd_add_user.handle()
async def handle_add_user(args: Message = CommandArg()):
    user_id = args.extract_plain_text().strip()
    if not user_id:
        await cmd_add_user.finish("Usage: /2fa_add_user [qq_id]")
    
    add_authorized_user(user_id)
    await cmd_add_user.finish(f"User {user_id} added to authorized list.")

@cmd_del_user.handle()
async def handle_del_user(args: Message = CommandArg()):
    user_id = args.extract_plain_text().strip()
    if not user_id:
        await cmd_del_user.finish("Usage: /2fa_del_user [qq_id]")
    
    remove_authorized_user(user_id)
    await cmd_del_user.finish(f"User {user_id} removed from authorized list.")

@cmd_list_users.handle()
async def handle_list_users():
    users = get_authorized_users()
    if not users:
        await cmd_list_users.finish("No authorized users.")
    await cmd_list_users.finish(f"Authorized Users:\n{', '.join(users)}")

@cmd_add_secret.handle()
async def handle_add_secret(args: Message = CommandArg()):
    # Format: /2fa_add [name] [url] [secret]
    # The user request said: /2fa_add EPFL {url} {secret}
    content = args.extract_plain_text().strip().split()
    if len(content) < 3:
        await cmd_add_secret.finish("Usage: /2fa_add [name] [url] [secret]")
    
    name = content[0].upper()
    url = content[1]
    secret = content[2]
    
    add_secret(name, url, secret)
    await cmd_add_secret.finish(f"Secret for '{name}' added/updated.")

@cmd_get_code.handle()
async def handle_get_code(event: MessageEvent, args: Message = CommandArg()):
    # Only allow private messages
    if not isinstance(event, PrivateMessageEvent):
        return

    user_id = event.get_user_id()
    
    # Check authorization
    if not is_authorized(user_id):
        # Do not reply if unauthorized
        return

    name = args.extract_plain_text().strip().upper()
    if not name:
        # If no name provided, maybe list available? Or just return.
        # User said: "send /2fa epfl or /2fa EPFL"
        return

    secret = get_secret(name)
    if not secret:
        # If secret not found, user spec says "For unavailable users, do not reply", 
        # but logic implies if user IS available but SECRET is not, what to do?
        # Safe bet: reply "Secret not found" to AUTHORIZED users.
        await cmd_get_code.finish(f"2FA entry '{name}' not found.")

    import time
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        totp = pyotp.TOTP(secret)
        code = totp.now()
        remaining = int(totp.interval - (time.time() % totp.interval))
    except Exception as e:
        await cmd_get_code.finish(f"Error generating code: {e}")

    now_gmt8 = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    await cmd_get_code.send(f"[{now_gmt8}]\nCurrent code for {name}: {code}\nRemaining time: {remaining}s")
    await cmd_get_code.finish(code)
