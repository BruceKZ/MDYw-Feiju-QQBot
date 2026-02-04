# -*- coding: utf-8 -*-
"""
视觉渲染引擎
WordCloud rendering with professional color schemes and high-quality output
"""
import io
import random
from typing import Dict, Optional

import numpy as np
from PIL import Image
from wordcloud import WordCloud
from matplotlib import cm

from .config import (
    FONT_PATH, 
    MASKS_DIR, 
    WORDCLOUD_CONFIG, 
    COLOR_SCHEMES,
    DARK_BACKGROUNDS
)

# ============== 形状蒙版生成器 ==============

def _create_circular_mask(size: int = 1000) -> np.ndarray:
    """生成圆形蒙版"""
    mask = np.ones((size, size), dtype=np.uint8) * 255
    cx, cy = size // 2, size // 2
    radius = size // 2 - 20
    y, x = np.ogrid[:size, :size]
    mask[(x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2] = 0
    return mask


def _create_rectangle_mask(width: int = 1200, height: int = 800) -> np.ndarray:
    """生成圆角矩形蒙版"""
    mask = np.ones((height, width), dtype=np.uint8) * 255
    margin = 30
    radius = 50  # 圆角半径
    
    # 填充主体矩形
    mask[margin + radius:height - margin - radius, margin:width - margin] = 0
    mask[margin:height - margin, margin + radius:width - margin - radius] = 0
    
    # 填充四个圆角
    for cy, cx in [(margin + radius, margin + radius),
                   (margin + radius, width - margin - radius),
                   (height - margin - radius, margin + radius),
                   (height - margin - radius, width - margin - radius)]:
        y, x = np.ogrid[:height, :width]
        mask[(x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2] = 0
    
    return mask


def _create_triangle_mask(size: int = 1000) -> np.ndarray:
    """生成三角形蒙版"""
    mask = np.ones((size, size), dtype=np.uint8) * 255
    margin = 50
    
    # 三角形顶点
    top = (size // 2, margin)
    left = (margin, size - margin)
    right = (size - margin, size - margin)
    
    for y in range(size):
        for x in range(size):
            # 检查点是否在三角形内
            def sign(p1, p2, p3):
                return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
            
            d1 = sign((x, y), top, left)
            d2 = sign((x, y), left, right)
            d3 = sign((x, y), right, top)
            
            has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
            has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
            
            if not (has_neg and has_pos):
                mask[y, x] = 0
    
    return mask


def _create_heart_mask(size: int = 1000) -> np.ndarray:
    """生成爱心形蒙版"""
    mask = np.ones((size, size), dtype=np.uint8) * 255
    cx, cy = size // 2, size // 2
    scale = size / 2.5
    
    for y in range(size):
        for x in range(size):
            # 心形方程: (x^2 + y^2 - 1)^3 - x^2 * y^3 < 0
            nx = (x - cx) / scale
            ny = -(y - cy) / scale + 0.3  # 上移一点
            
            value = (nx ** 2 + ny ** 2 - 1) ** 3 - nx ** 2 * ny ** 3
            if value < 0:
                mask[y, x] = 0
    
    return mask


def _create_star_mask(size: int = 1000, points: int = 5) -> np.ndarray:
    """生成星形蒙版"""
    mask = np.ones((size, size), dtype=np.uint8) * 255
    cx, cy = size // 2, size // 2
    outer_r = size // 2 - 30
    inner_r = outer_r * 0.4
    
    import math
    
    # 计算星形顶点
    vertices = []
    for i in range(points * 2):
        angle = math.pi / 2 + i * math.pi / points
        r = outer_r if i % 2 == 0 else inner_r
        vx = cx + r * math.cos(angle)
        vy = cy - r * math.sin(angle)
        vertices.append((vx, vy))
    
    # 使用多边形填充
    from PIL import Image, ImageDraw
    img = Image.new('L', (size, size), 255)
    draw = ImageDraw.Draw(img)
    draw.polygon(vertices, fill=0)
    
    return np.array(img)


def _create_cat_mask(size: int = 1000) -> np.ndarray:
    """生成猫咪头形蒙版"""
    from PIL import Image, ImageDraw
    
    img = Image.new('L', (size, size), 255)
    draw = ImageDraw.Draw(img)
    
    cx, cy = size // 2, size // 2 + 50
    head_r = size // 3
    
    # 头部 (椭圆)
    draw.ellipse([cx - head_r, cy - head_r * 0.8, cx + head_r, cy + head_r], fill=0)
    
    # 左耳 (三角形)
    ear_size = head_r * 0.6
    draw.polygon([
        (cx - head_r * 0.7, cy - head_r * 0.5),
        (cx - head_r * 0.3, cy - head_r * 0.6),
        (cx - head_r * 0.5, cy - head_r * 1.2)
    ], fill=0)
    
    # 右耳 (三角形)
    draw.polygon([
        (cx + head_r * 0.7, cy - head_r * 0.5),
        (cx + head_r * 0.3, cy - head_r * 0.6),
        (cx + head_r * 0.5, cy - head_r * 1.2)
    ], fill=0)
    
    return np.array(img)


# 可用形状列表及权重
SHAPE_GENERATORS = [
    ("circle", _create_circular_mask, 25),      # 25% 圆形
    ("rectangle", _create_rectangle_mask, 20),  # 20% 矩形
    ("triangle", _create_triangle_mask, 15),    # 15% 三角形
    ("heart", _create_heart_mask, 15),          # 15% 爱心
    ("star", _create_star_mask, 15),            # 15% 星形
    ("cat", _create_cat_mask, 10),              # 10% 猫咪
]


def _get_random_mask() -> tuple:
    """随机选择并生成一个形状蒙版"""
    # 按权重随机选择
    total_weight = sum(w for _, _, w in SHAPE_GENERATORS)
    r = random.randint(1, total_weight)
    
    cumulative = 0
    for name, generator, weight in SHAPE_GENERATORS:
        cumulative += weight
        if r <= cumulative:
            mask = generator()
            print(f"[WordCloud] Using shape: {name}")
            return name, mask
    
    # 默认返回圆形
    return "circle", _create_circular_mask()


def _load_mask(mask_name: str = None) -> Optional[np.ndarray]:
    """
    加载或生成蒙版
    如果不指定名称，随机生成一个形状
    """
    if mask_name:
        mask_path = MASKS_DIR / mask_name
        if mask_path.exists():
            try:
                img = Image.open(mask_path).convert("L")
                return np.array(img)
            except Exception as e:
                print(f"[WordCloud] Failed to load mask {mask_path}: {e}")
    
    # 随机生成形状
    _, mask = _get_random_mask()
    return mask


def _get_colormap_func(colormap_name: str):
    """
    从 Matplotlib colormap 创建颜色函数
    返回可用于 WordCloud color_func 的函数
    """
    cmap = cm.get_cmap(colormap_name)
    
    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        # 随机采样 colormap (0.2-0.9 范围，避免太暗或太亮)
        value = random.uniform(0.2, 0.9)
        rgba = cmap(value)
        # 转换为 RGB hex
        r, g, b = int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
        return f"rgb({r}, {g}, {b})"
    
    return color_func


def _select_color_scheme() -> str:
    """
    随机选择配色方案
    从预定义的 colormap 列表中随机选择
    """
    all_colormaps = []
    for scheme_maps in COLOR_SCHEMES.values():
        all_colormaps.extend(scheme_maps)
    
    return random.choice(all_colormaps)


def generate_wordcloud(
    word_frequencies: Dict[str, int],
    use_mask: bool = True,
    transparent_bg: bool = True
) -> Optional[bytes]:
    """
    生成词云图片
    
    Args:
        word_frequencies: 词频字典 {word: count}
        use_mask: 是否使用蒙版形状
        transparent_bg: 是否使用透明背景
    
    Returns:
        PNG 图片的 bytes，失败返回 None
    """
    if not word_frequencies:
        return None
    
    # 检查字体
    font_path = str(FONT_PATH)
    if not FONT_PATH.exists():
        print(f"[WordCloud] Font not found: {font_path}")
        # 尝试系统字体
        import platform
        if platform.system() == "Windows":
            font_path = "C:\\Windows\\Fonts\\msyh.ttc"
        else:
            font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
    
    # 配置参数
    config = WORDCLOUD_CONFIG.copy()
    config["font_path"] = font_path
    
    # 加载蒙版
    if use_mask:
        mask = _load_mask()
        if mask is not None:
            config["mask"] = mask
            # 使用蒙版时需要调整宽高
            config["width"] = mask.shape[1]
            config["height"] = mask.shape[0]
    
    # 背景设置
    if transparent_bg:
        config["background_color"] = None
        config["mode"] = "RGBA"
    else:
        config["background_color"] = random.choice(DARK_BACKGROUNDS)
        config["mode"] = "RGB"
    
    # 选择配色并创建颜色函数
    colormap_name = _select_color_scheme()
    color_func = _get_colormap_func(colormap_name)
    
    try:
        # 创建词云
        wc = WordCloud(**config)
        wc.generate_from_frequencies(word_frequencies)
        wc.recolor(color_func=color_func)
        
        # 转换为图片 bytes
        img = wc.to_image()
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        
        print(f"[WordCloud] Generated with colormap: {colormap_name}, words: {len(word_frequencies)}")
        return buffer.getvalue()
        
    except Exception as e:
        print(f"[WordCloud] Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_wordcloud_simple(
    word_frequencies: Dict[str, int],
    background_color: str = "#1a1a1a"
) -> Optional[bytes]:
    """
    简化版词云生成
    不使用蒙版，固定深色背景
    适用于快速生成或蒙版出问题时的降级方案
    """
    if not word_frequencies:
        return None
    
    font_path = str(FONT_PATH) if FONT_PATH.exists() else None
    
    try:
        wc = WordCloud(
            font_path=font_path,
            width=1000,
            height=600,
            background_color=background_color,
            max_words=150,
            min_font_size=10,
            collocations=False,
            colormap=_select_color_scheme()
        )
        wc.generate_from_frequencies(word_frequencies)
        
        buffer = io.BytesIO()
        wc.to_image().save(buffer, format="PNG")
        return buffer.getvalue()
        
    except Exception as e:
        print(f"[WordCloud] Simple generation failed: {e}")
        return None
