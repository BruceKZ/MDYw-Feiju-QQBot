# -*- coding: utf-8 -*-
"""
生成默认蒙版图片
Run this script to generate the default circular mask
"""
from PIL import Image
import numpy as np
from pathlib import Path

def generate_circular_mask(size: int = 1000, output_path: str = None):
    """
    生成圆形蒙版
    白底 (255) + 黑色圆形区域 (0)
    """
    mask = np.ones((size, size), dtype=np.uint8) * 255
    
    cx, cy = size // 2, size // 2
    radius = size // 2 - 10
    
    y, x = np.ogrid[:size, :size]
    mask_area = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
    mask[mask_area] = 0
    
    img = Image.fromarray(mask)
    
    if output_path:
        img.save(output_path)
        print(f"Mask saved to {output_path}")
    
    return img


if __name__ == "__main__":
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    masks_dir = script_dir / "resources" / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = masks_dir / "default_mask.png"
    generate_circular_mask(1000, str(output_path))
