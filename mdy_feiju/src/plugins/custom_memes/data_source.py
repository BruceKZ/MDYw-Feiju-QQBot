from typing import Optional, Tuple, List, Union
import imagehash
import json
import base64
import hashlib
from PIL import Image
from io import BytesIO
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from . import db
from .utils import resize_image, download_url

class MemeManager:
    @staticmethod
    def get_meme(trigger_text: str, context_id: str) -> Tuple[Optional[Union[Message, MessageSegment]], str]:
        """
        Find a meme based on trigger text using prefix matching.
        Returns (message_or_segment, matched_name).
        """
        # Prefix Maximum Matching
        for i in range(len(trigger_text), 0, -1):
            potential_name = trigger_text[:i].strip()
            if not potential_name:
                continue
                
            # Try to find in current group
            lib_id = db.get_library_id(potential_name.lower(), context_id)
            
            if lib_id:
                data, meme_type = db.get_random_image(lib_id)
                if data:
                    if meme_type == "image":
                        return MessageSegment.image(data), potential_name
                    elif meme_type == "mixed":
                        try:
                            # Deserialize mixed content
                            content_list = json.loads(data.decode("utf-8"))
                            msg = Message()
                            for seg in content_list:
                                if seg["type"] == "text":
                                    msg.append(MessageSegment.text(seg["data"]["text"]))
                                elif seg["type"] == "image":
                                    img_bytes = base64.b64decode(seg["data"]["file"])
                                    msg.append(MessageSegment.image(img_bytes))
                            return msg, potential_name
                        except Exception as e:
                            print(f"Error deserializing mixed meme: {e}")
                            return None, ""
                    
        return None, ""

    @staticmethod
    def get_all_memes(context_id: str) -> List[str]:
        """
        Get all meme/library names for the current context.
        Returns a formatted strings list.
        """
        libs = db.get_all_library_names(context_id)
        
        formatted_names = []
        for primary, aliases in libs:
            if aliases:
               formatted_names.append(f"{primary} (别名: {', '.join(aliases)})")
            else:
               formatted_names.append(primary)
               
        return formatted_names

    @staticmethod
    async def add_meme(category_name: str, message: Message, context_id: str, force: bool = False) -> Tuple[str, Optional[bytes]]:
        """
        Add a meme to the library.
        Returns (result_message, duplicate_image_data).
        If duplicate_image_data is not None, means a duplicate was found.
        """
        try:
            # Filter supported segments (text and image)
            segments = []
            for seg in message:
                if seg.type == "text" and seg.data["text"].strip():
                    segments.append(seg)
                elif seg.type == "image":
                    segments.append(seg)
            
            if not segments:
                return "没有有效内容（文本或图片），添加失败。", None

            # Determine type
            # If single image and no text -> legacy "image" type
            if len(segments) == 1 and segments[0].type == "image":
                return await MemeManager._add_image_type(category_name, segments[0], context_id, force)
            else:
                return await MemeManager._add_mixed_type(category_name, segments, context_id, force)

        except Exception as e:
            return f"添加失败：{e}", None

    @staticmethod
    async def _add_image_type(category_name: str, segment: MessageSegment, context_id: str, force: bool) -> Tuple[str, Optional[bytes]]:
        img_url = segment.data.get("url")
        raw_img_data = await download_url(img_url)
        
        # Resize image
        final_img_data = resize_image(raw_img_data)
        
        # Calculate hash
        check_img = Image.open(BytesIO(final_img_data))
        new_hash = str(imagehash.dhash(check_img))
        
        # Get or Create Library
        lib_id = db.get_library_id(category_name.lower(), context_id)
        if not lib_id:
            lib_id = db.create_library(category_name.lower(), context_id)
            
        # Check duplicates
        if not force:
            is_dup, dup_img = db.check_duplicate(lib_id, new_hash, meme_type="image")
            if is_dup:
                return "水过了！你老冯的\n瞪大你的狗眼看看是不是这个：", dup_img
        
        db.add_image(lib_id, final_img_data, new_hash, meme_type="image")
        return f"成功添加{category_name}！", None

    @staticmethod
    async def _add_mixed_type(category_name: str, segments: List[MessageSegment], context_id: str, force: bool) -> Tuple[str, Optional[bytes]]:
        serialized_segs = []
        
        for seg in segments:
            if seg.type == "text":
                serialized_segs.append({
                    "type": "text",
                    "data": {"text": seg.data["text"]}
                })
            elif seg.type == "image":
                img_url = seg.data.get("url")
                raw_data = await download_url(img_url)
                final_data = resize_image(raw_data)
                b64_data = base64.b64encode(final_data).decode("utf-8")
                serialized_segs.append({
                    "type": "image",
                    "data": {"file": b64_data}
                })
        
        json_data = json.dumps(serialized_segs, ensure_ascii=False)
        data_bytes = json_data.encode("utf-8")
        
        # MD5 hash for exact matching of mixed content
        new_hash = hashlib.md5(data_bytes).hexdigest()
        
        # Get or Create Library
        lib_id = db.get_library_id(category_name.lower(), context_id)
        if not lib_id:
            lib_id = db.create_library(category_name.lower(), context_id)
            
        # Check duplicates
        if not force:
            is_dup, dup_img = db.check_duplicate(lib_id, new_hash, meme_type="mixed")
            if is_dup:
                # For mixed type duplicate, we might need to handle the return differently 
                # since dup_img is the JSON data.
                # But existing handlers expect bytes for image.
                # Let's render it? Or just return text?
                # For simplicity, we can let the handler try to display it, 
                # but handlers.py expects image bytes to wrap in MessageSegment.image.
                # We should probably return None or handle it in handler.
                # To be consistent with existing logic, let's just return the data bytes,
                # and let the handler (which we will update) handle it.
                return "水过了！内容完全一致。", dup_img

        db.add_image(lib_id, data_bytes, new_hash, meme_type="mixed")
        return f"成功添加{category_name}！", None

    @staticmethod
    async def delete_meme(category_name: str, message: Message, context_id: str) -> str:
        try:
            # Filter supported segments (text and image)
            segments = []
            for seg in message:
                if seg.type == "text" and seg.data["text"].strip():
                    segments.append(seg)
                elif seg.type == "image":
                    segments.append(seg)
            
            if not segments:
                return "不支持的消息类型，无法删除。"

            target_hash = ""
            meme_type = "image"

            # Determine type (same logic as add)
            if len(segments) == 1 and segments[0].type == "image":
                meme_type = "image"
                img_url = segments[0].data.get("url")
                target_img_data = await download_url(img_url)
                target_img = Image.open(BytesIO(target_img_data))
                target_hash = str(imagehash.dhash(target_img))
            else:
                meme_type = "mixed"
                serialized_segs = []
                for seg in segments:
                    if seg.type == "text":
                        serialized_segs.append({
                            "type": "text",
                            "data": {"text": seg.data["text"]}
                        })
                    elif seg.type == "image":
                        img_url = seg.data.get("url")
                        raw_data = await download_url(img_url)
                        final_data = resize_image(raw_data)
                        b64_data = base64.b64encode(final_data).decode("utf-8")
                        serialized_segs.append({
                            "type": "image",
                            "data": {"file": b64_data}
                        })
                
                json_data = json.dumps(serialized_segs, ensure_ascii=False)
                data_bytes = json_data.encode("utf-8")
                target_hash = hashlib.md5(data_bytes).hexdigest()

            lib_id = db.get_library_id(category_name.lower(), context_id)
            deleted = False
            
            if lib_id:
                deleted = db.delete_image_by_hash(lib_id, target_hash, meme_type=meme_type)
            
            if deleted:
                return f"已删除！{category_name}House"
            else:
                return f"{category_name}已经被爱死了..."

        except Exception as e:
            return f"删除失败：{e}，{category_name}别走😭"

    @staticmethod
    def sync_memes(source_group: str, target_group: str, keyword: str) -> str:
        """
        Sync memes from source group to target group for a specific keyword.
        """
        def parse_context(raw: str) -> str:
            if raw.lower().startswith('p'):
                return f"private_{raw[1:]}"
            return raw

        src_ctx = parse_context(source_group)
        tgt_ctx = parse_context(target_group)
        
        # 1. Check Source Category
        source_lib_id = db.get_library_id(keyword.lower(), src_ctx)
        if not source_lib_id:
            return f"源 ({src_ctx}) 没有关于 '{keyword}' 的图片。"
            
        # 2. Get Source Images
        images = db.get_all_images(source_lib_id)
        if not images:
            return f"源 ({src_ctx}) 的 '{keyword}' 是空的。"
            
        # 3. Get/Create Target Category
        target_lib_id = db.get_library_id(keyword.lower(), tgt_ctx)
        if not target_lib_id:
            target_lib_id = db.create_library(keyword.lower(), tgt_ctx)
            
        # 4. Sync
        count = 0
        skipped = 0
        
        for img_data, img_phash, img_type in images:
            is_dup, _ = db.check_duplicate(target_lib_id, img_phash, meme_type=img_type)
            if is_dup:
                skipped += 1
                continue
                
            db.add_image(target_lib_id, img_data, img_phash, meme_type=img_type)
            count += 1
            
        return f"同步完成！\n关键字: {keyword}\n成功同步: {count} 张\n跳过重复: {skipped} 张"
