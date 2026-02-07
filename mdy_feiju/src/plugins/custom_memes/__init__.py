from nonebot import on_regex, on_startswith, get_driver, on_command
from . import handlers
from . import alias

# Initialize DB on startup
driver = get_driver()
driver.on_startup(handlers.init_data)

# --- Command Matchers ---

# 1. Get Meme: "来只xxx" or "来个xxx"
get_meme_cmd = on_regex(r"^来[只个点](.+)$", priority=10, block=True)
get_meme_cmd.handle()(handlers.handle_get_meme)

# 2. Add Meme: "添加xxx"
add_meme_cmd = on_startswith("添加", priority=10, block=True)
add_meme_cmd.handle()(handlers.handle_add_meme)

# 3. Delete Meme: "删除xxx"
del_meme_cmd = on_startswith("删除", priority=10, block=True)
del_meme_cmd.handle()(handlers.handle_delete_meme)

# 4. Sync Meme: "/sync source_group target_group keyword" (Superuser & Private only)
sync_cmd = on_command("同步", priority=5, block=True)
sync_cmd.handle()(handlers.handle_sync)

# 5. Add Alias: "添加别名 existing_name alias_name"
add_alias_cmd = on_startswith("添加别名", priority=5, block=True)
add_alias_cmd.handle()(alias.handle_add_alias)

# 6. Delete Alias: "删除别名 alias_name"
del_alias_cmd = on_startswith("删除别名", priority=5, block=True)
del_alias_cmd.handle()(alias.handle_del_alias)

# 7. List Aliases: "查看别名 name"
list_alias_cmd = on_startswith("查看别名", priority=10, block=True)
list_alias_cmd.handle()(alias.handle_list_alias)

# 8. Help: "/help"
help_cmd = on_command("有啥花活", priority=10, block=True)
help_cmd.handle()(handlers.handle_help)
