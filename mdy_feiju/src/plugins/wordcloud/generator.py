import io
import jieba
from wordcloud import WordCloud
import platform
from pathlib import Path

# Common stop words
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "怎么", "我们", "这", "那", "吗", "吧", "啊", "哦", "嗯", "呢", "哈", "呀", "什么", "因为", "所以", "如果", "但是", "图片", "表情", "video", "image"
}

def get_font_path():
    system = platform.system()
    if system == "Windows":
        return "C:\\Windows\\Fonts\\msyh.ttc"
    elif system == "Darwin":
        return "/System/Library/Fonts/PingFang.ttc"
    else:
        # Linux / Docker: need to check available fonts or use a bundled one
        # Check for font file in the plugin dir
        plugin_dir = Path(__file__).parent
        for font_name in ["font.ttf", "simhei.ttf", "SimHei.ttf", "msyh.ttc", "msyh.ttf"]:
            local_font = plugin_dir / font_name
            if local_font.exists():
                return str(local_font)
            
        # Fallback to system font assumption or standard paths
        # Some docker images might have fonts in /usr/share/fonts
        import os
        if os.path.exists("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"):
            return "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
        
        return "simhei.ttf" # Last resort, requires system installation

def generate_word_cloud(texts: list[str]) -> bytes:
    if not texts:
        return None
        
    full_text = " ".join(texts)
    
    # Segment words
    words = jieba.lcut(full_text)
    
    # Filter stop words and short words
    filtered_words = [w for w in words if len(w) > 1 and w not in STOP_WORDS]
    
    if not filtered_words:
        return None
        
    text_for_cloud = " ".join(filtered_words)
    
    # Generate Word Cloud
    font_path = get_font_path()
    print(f"DEBUG: Using font path: {font_path}")
    
    wc = WordCloud(
        font_path=font_path,
        width=800,
        height=600,
        background_color="white",
        max_words=200,
        stopwords=STOP_WORDS
    )
    
    try:
        wc.generate(text_for_cloud)
        
        # Save to BytesIO
        img_buffer = io.BytesIO()
        wc.to_image().save(img_buffer, format="PNG")
        return img_buffer.getvalue()
    except Exception as e:
        print(f"Error generating word cloud: {e}")
        return "caonima"
