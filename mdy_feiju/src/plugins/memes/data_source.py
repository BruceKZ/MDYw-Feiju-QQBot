from typing import Optional, Tuple, List
import imagehash
from PIL import Image
from io import BytesIO

from . import db
from .utils import resize_image, download_url

class MemeManager:
    @staticmethod
    def get_meme(trigger_text: str, context_id: str) -> Tuple[Optional[bytes], str]:
        """
        Find a meme based on trigger text using prefix matching.
        Returns (image_data, matched_name).
        """
        # Prefix Maximum Matching
        for i in range(len(trigger_text), 0, -1):
            potential_name = trigger_text[:i].strip()
            if not potential_name:
                continue
                
            # Try to find in current group
            lib_id = db.get_library_id(potential_name.lower(), context_id)
            
            if lib_id:
                img_data = db.get_random_image(lib_id)
                if img_data:
                    return img_data, potential_name
        
        return None, ""

    @staticmethod
    async def add_meme(category_name: str, img_url: str, context_id: str) -> str:
        try:
            raw_img_data = await download_url(img_url)
                
            # Resize image
            final_img_data = resize_image(raw_img_data)
            
            # Calculate hash
            check_img = Image.open(BytesIO(final_img_data))
            new_hash = str(imagehash.phash(check_img))
            
            # Get or Create Category
            lib_id = db.get_library_id(category_name.lower(), context_id)
            if not lib_id:
                lib_id = db.create_library(category_name.lower(), context_id)
                
            # Check duplicates
            if db.check_duplicate(lib_id, new_hash):
                return "水过了！你老冯的"
            
            db.add_image(lib_id, final_img_data, new_hash)
            return f"成功添加{category_name}！"

        except Exception as e:
            return f"添加失败：{e}"

    @staticmethod
    async def delete_meme(category_name: str, img_url: str, context_id: str) -> str:
        try:
            target_img_data = await download_url(img_url)
            
            target_img = Image.open(BytesIO(target_img_data))
            target_hash = str(imagehash.phash(target_img))

            lib_id = db.get_library_id(category_name.lower(), context_id)
            deleted = False
            
            if lib_id:
                deleted = db.delete_image_by_hash(lib_id, target_hash)
            
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
        
        for img_data, img_phash in images:
            if db.check_duplicate(target_lib_id, img_phash):
                skipped += 1
                continue
                
            db.add_image(target_lib_id, img_data, img_phash)
            count += 1
            
        return f"同步完成！\n关键字: {keyword}\n成功同步: {count} 张\n跳过重复: {skipped} 张"
