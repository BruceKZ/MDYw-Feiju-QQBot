# -*- coding: utf-8 -*-
"""
词云插件配置模块
Configuration module for wordcloud plugin
"""
from pathlib import Path

# 插件根目录
PLUGIN_DIR = Path(__file__).parent

# 资源目录
RESOURCES_DIR = PLUGIN_DIR / "resources"
FONTS_DIR = RESOURCES_DIR / "fonts"
MASKS_DIR = RESOURCES_DIR / "masks"
STOPWORDS_DIR = RESOURCES_DIR / "stopwords"

# 字体配置
FONT_PATH = FONTS_DIR / "simhei.ttf"

# 用户自定义词典 (用于添加新词/网络用语)
USER_DICT_PATH = RESOURCES_DIR / "user_dict.txt"

# 数据库配置
DATA_DIR = Path("data/wordcloud")
DB_FILE = DATA_DIR / "messages.db"

# 词云生成参数 (严格按照 taskbook 规范)
WORDCLOUD_CONFIG = {
    "scale": 3,                    # 3倍采样，保证放大不糊
    "width": 1000,                 # 基础画布宽度
    "height": 1000,                # 基础画布高度
    "max_words": 150,              # 词数上限，防止视觉拥挤
    "min_font_size": 10,           # 避免不可读微型字
    "prefer_horizontal": 0.9,      # 90%横排提升可读性
    "relative_scaling": 0.6,       # 词频与字号相关性
    "collocations": False,         # 关闭词组搭配防止重复
    "mode": "RGBA",                # 透明背景支持
    "background_color": None,      # 透明背景
}

# 配色方案 (Matplotlib Colormaps)
COLOR_SCHEMES = {
    "tech_cool": ["viridis", "mako", "cividis"],       # 科技/冷色调
    "warm_vibrant": ["magma", "plasma", "inferno"],    # 活力/暖色调
}

# 深色背景选项 (搭配透明背景时备用)
DARK_BACKGROUNDS = ["#101010", "#1a1a1a", "#0f0f0f", "#0d1117"]

# 缓存配置
CACHE_EXPIRE_SECONDS = 30

# CD 限制 (秒)
COOLDOWN_SECONDS = 30
