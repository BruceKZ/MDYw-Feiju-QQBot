from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher

from . import db
from .utils import get_context_id

class AliasManager:
    @staticmethod
    def add_alias(real_name: str, alias_name: str, context_id: str) -> str:
        name1 = real_name.lower()
        name2 = alias_name.lower()
        
        if name1 == name2:
            return "别名不能和原名一样"

        lib1_id = db.get_library_id(name1, context_id)
        lib2_id = db.get_library_id(name2, context_id)
        
        # Case 1: Both exist
        if lib1_id and lib2_id:
            if lib1_id == lib2_id:
                 return f"'{name1}' 和 '{name2}' 已经是同一个图库了。"
                 
            # Different libraries -> Merge
            try:
                db.merge_libraries(lib2_id, lib1_id)
                return f"检测到 '{name1}' 和 '{name2}' 都有图库，已将它们合并！\n现在 '{name2}' 的图也都归 '{name1}' 啦。"
            except Exception as e:
                return f"合并失败：{e}"
                
        # Case 2: Only 1 exists (Add alias)
        elif lib1_id and not lib2_id:
            if db.add_name_to_library(name2, lib1_id, context_id):
                return f"成功！以后叫 '{name2}' 也可以。"
            else:
                 return f"添加失败。"
                 
        elif not lib1_id and lib2_id:
            db.add_name_to_library(name1, lib2_id, context_id)
            return f"成功！以后叫 '{name1}' 也可以。"
                 
        # Case 3: Neither exists
        else:
            return f"找不到 '{name1}' 也没有 '{name2}'，你先添加点图呗？"

    @staticmethod
    def remove_alias(target_name: str, context_id: str) -> str:
        target_name = target_name.lower()
        lib_id = db.get_library_id(target_name, context_id)
        if not lib_id:
            return f"找不到 '{target_name}'"
            
        try:
            # Check if it's the last name
            all_names = db.get_library_names(lib_id)
            if len(all_names) <= 1:
                return f"'{target_name}' 是这个图库唯一的这类名字了，删了就找不到了！"
                
            if db.remove_name(target_name, context_id):
                return f"已删除名字 '{target_name}'"
            else:
                return f"删除失败。"
        except Exception as e:
            return f"删除失败：{e}"
            
    @staticmethod
    def list_aliases(name: str, context_id: str) -> str:
        name = name.lower()
        lib_id = db.get_library_id(name, context_id)
        if not lib_id:
            return f"找不到图库 '{name}'"
            
        names = db.get_library_names(lib_id)
        if names:
            names_str = "、".join(names)
            return f"这个图库的名字有：\n{names_str}"
        else:
            return f"怪事，没名字？"

#Handlers
async def handle_add_alias(matcher: Matcher, event: MessageEvent):
    # on_startswith("添加别名")
    msg = event.get_plaintext().strip()
    args_str = msg[len("添加别名"):].strip()
    args = args_str.split()
    
    if len(args) != 2:
        await matcher.finish("格式：添加别名 <原名> <别名>")
        return
        
    real_name = args[0]
    alias_name = args[1]
    
    context_id = get_context_id(event)
    result = AliasManager.add_alias(real_name, alias_name, context_id)
    await matcher.finish(result)

async def handle_del_alias(matcher: Matcher, event: MessageEvent):
    # on_startswith("删除别名")
    msg = event.get_plaintext().strip()
    target_name = msg[len("删除别名"):].strip()
    
    if not target_name:
        await matcher.finish("不说名字我删个der？猪吧")
        return

    context_id = get_context_id(event)
    result = AliasManager.remove_alias(target_name, context_id)
    await matcher.finish(result)

async def handle_list_alias(matcher: Matcher, event: MessageEvent):
    # on_startswith("查看别名")
    msg = event.get_plaintext().strip()
    name = msg[len("查看别名"):].strip()
    
    if not name:
        await matcher.finish("查哪个你说啊？")
        return
        
    context_id = get_context_id(event)
    result = AliasManager.list_aliases(name, context_id)
    await matcher.finish(result)
