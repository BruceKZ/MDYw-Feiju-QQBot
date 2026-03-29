import io
import httpx
import time
from datetime import datetime
from nonebot_plugin_imageutils import BuildImage, Text2Image
from PIL import Image

# Codeforces Rating Colors
RGBColor = tuple[int, int, int]

def make_text(text: str, size: int, fill: RGBColor | str = "black", weight: str = "normal", underline: bool = False) -> Image.Image:
    from PIL import ImageDraw
    # Force loading exact high-end fonts native to CF
    fonts = ["Helvetica Neue", "Microsoft YaHei", "Segoe UI Emoji"]
    img = Text2Image.from_text(text, size, fill=fill, weight=weight, fallback_fonts=fonts).to_image()
    if underline:
        draw = ImageDraw.Draw(img)
        line_y = img.height - max(1, size // 15)
        line_width = max(1, size // 20)
        draw.line((0, line_y, img.width, line_y), fill=fill, width=line_width)
    return img

def get_color(rating: int) -> RGBColor:
    if rating == 0:
        return (0, 0, 0) # Unrated / Black
    elif rating < 1200:
        return (128, 128, 128) # Newbie - Gray
    elif rating < 1400:
        return (0, 128, 0) # Pupil - Green
    elif rating < 1600:
        return (3, 168, 158) # Specialist - Cyan
    elif rating < 1900:
        return (0, 0, 255) # Expert - Blue
    elif rating < 2100:
        return (170, 0, 170) # Candidate Master - Violet
    elif rating < 2300:
        return (255, 140, 0) # Master - Orange
    elif rating < 2400:
        return (255, 140, 0) # International Master - Orange
    elif rating < 2600:
        return (255, 0, 0) # Grandmaster - Red
    elif rating < 3000:
        return (255, 0, 0) # International Grandmaster - Red
    else:
        return (255, 0, 0) # Legendary Grandmaster - Red

def relative_time(ts: int) -> str:
    now = int(time.time())
    diff = max(0, now - ts)
    if diff < 60:
        return "Just now"
    elif diff < 3600:
        m = diff // 60
        return f"{(m)} minute{'s' if m > 1 else ''} ago"
    elif diff < 86400:
        h = diff // 3600
        return f"{(h)} hour{'s' if h > 1 else ''} ago"
    elif diff < 30 * 86400:
        d = diff // 86400
        return f"{(d)} day{'s' if d > 1 else ''} ago"
    elif diff < 365 * 86400:
        mo = diff // (30 * 86400)
        return f"{(mo)} month{'s' if mo > 1 else ''} ago"
    else:
        y = diff // (365 * 86400)
        return f"{(y)} year{'s' if y > 1 else ''} ago"

async def fetch_avatar(url: str) -> BuildImage:
    if not url.startswith("http"):
        url = "https:" + url
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            return BuildImage.new("RGBA", (150, 150), (200, 200, 200, 255))
        return BuildImage.open(io.BytesIO(resp.content))

async def draw_cf_card(user_info: dict, percent: float | None, cache_time = None) -> bytes:
    rating = user_info.get("rating", 0)
    max_rating = user_info.get("maxRating", 0)
    title = user_info.get("rank", "unrated").title()
    max_title = user_info.get("maxRank", "unrated").title()
    handle = user_info.get("handle", "Unknown")
    
    title_color = get_color(rating)
    is_lgm = rating >= 3000
    
    lines_to_draw = []
    current_y = 30
    max_text_width = 0
    text_x = 30
    
    def add_line(elements, margin_bottom=15):
        nonlocal current_y, max_text_width
        current_x = text_x
        row_height = max((img.height for img, dx, dy in elements if img), default=0)
        # OS fonts sometimes report strict inner bounding boxes; we force a 1.3x line-height multiplier
        visual_height = int(row_height * 1.3)
        
        for (img, x_offset, y_offset) in elements:
            if img:
                # Align elements in the same row by their bottom edge
                y_align = row_height - img.height
                lines_to_draw.append((img, current_x + x_offset, current_y + y_align + y_offset))
                current_x += img.width + x_offset
                
        max_text_width = max(max_text_width, current_x - text_x)
        current_y += visual_height + margin_bottom

    # 1. Title (Top Title colored + bold)
    if is_lgm and len(title) > 0:
        add_line([
            (make_text(title[0], 28, fill="black", weight="bold"), 0, 0),
            (make_text(title[1:], 28, fill=title_color, weight="bold"), 0, 0)
        ], margin_bottom=4)
    else:
        add_line([
            (make_text(title, 28, fill=title_color, weight="bold"), 0, 0)
        ], margin_bottom=4)
        
    # 2. Handle (Large, colored + bold)
    if is_lgm and len(handle) > 0:
        add_line([
            (make_text(handle[0], 48, fill="black", weight="bold"), 0, 0),
            (make_text(handle[1:], 48, fill=title_color, weight="bold"), 0, 0)
        ], margin_bottom=16)
    else:
        add_line([
            (make_text(handle, 48, fill=title_color, weight="bold"), 0, 0)
        ], margin_bottom=16)
        
    # 3. Name, City, Country
    name_parts = []
    n_str = " ".join(filter(None, [user_info.get("firstName"), user_info.get("lastName")]))
    if n_str:
        name_parts.append((make_text(n_str, 22, fill=(100, 100, 100)), 0, 0)) # Grey, not bold
        
    city = user_info.get("city")
    if city:
        if name_parts:
            name_parts.append((make_text(", ", 22, fill=(100, 100, 100)), 0, 0))
        name_parts.append((make_text(city, 22, fill="#0000ee", underline=True), 0, 0)) # Blue underline
        
    country = user_info.get("country")
    if country:
        if name_parts:
            name_parts.append((make_text(", ", 22, fill=(100, 100, 100)), 0, 0))
        name_parts.append((make_text(country, 22, fill="#0000ee", underline=True), 0, 0)) # Blue underline
        
    if name_parts:
        add_line(name_parts, margin_bottom=10)
        
    # 4. Organization
    org = user_info.get("organization")
    if org:
        add_line([
            (make_text("From ", 22, fill="black"), 0, 0),
            (make_text(org, 22, fill="#0000ee", underline=True), 0, 0) # Blue underline
        ], margin_bottom=16)
    else:
        if name_parts: current_y += 12
        
    # 5. Rating block
    if rating > 0:
        rating_label = make_text("Contest rating: ", 20, fill="black")
        rating_val = make_text(str(rating), 20, fill=title_color, weight="bold")
        elements = [(rating_label, 0, 0), (rating_val, 0, 0)]
        
        if max_rating > 0:
            max_c = get_color(max_rating)
            elements.extend([
                (make_text("  (max. ", 20, fill="black"), 0, 0),
                (make_text(max_title, 20, fill=max_c, weight="bold"), 0, 0),
                (make_text(", ", 20, fill="black"), 0, 0),
                (make_text(str(max_rating), 20, fill=max_c, weight="bold"), 0, 0),
                (make_text(")", 20, fill="black"), 0, 0)
            ])
        add_line(elements, margin_bottom=7)
    
    # 6. Percentile block
    if percent is not None and rating > 0:
        add_line([
            (make_text(f"Top {percent:.2f}% of active users", 20, fill="black"), 0, 0)
        ], margin_bottom=7)
        
    # Inject a subtle horizontal gray divider with strictly verified geometric symmetry
    current_y += 2
    divider_y = current_y
    current_y += 15
        
    # 7. Last visit
    last_visit = user_info.get("lastOnlineTimeSeconds")
    if last_visit:
        add_line([
            (make_text("Last visit: ", 20, fill="black"), 0, 0),
            (make_text(relative_time(last_visit), 20, fill="black"), 0, 0)
        ], margin_bottom=7)
        
    # 8. Registered
    reg_time = user_info.get("registrationTimeSeconds")
    if reg_time:
        add_line([
            (make_text("Registered: ", 20, fill="black"), 0, 0),
            (make_text(relative_time(reg_time), 20, fill="black"), 0, 0)
        ], margin_bottom=7)
        
    # After generating all texts, current_y is the bottom of the text block.
    # text_height is current_y - 30 (since text starts at y=30)
    text_height = current_y - 30
    
    # Handle Avatar
    avatar_url = user_info.get("titlePhoto") or user_info.get("avatar")
    avatar_img = None
    avatar_width, avatar_height = 0, 0
    
    if avatar_url:
        avatar = await fetch_avatar(avatar_url)
        avatar = avatar.convert("RGBA")
        # Scale to match text height perfectly, preserving aspect ratio
        ratio = text_height / avatar.height
        avatar_height = text_height
        avatar_width = int(avatar.width * ratio)
        avatar_img = avatar.resize((avatar_width, avatar_height))
    else:
        # Default placeholder
        avatar_width = text_height
        avatar_height = text_height

    # Scale background width (max text width + spacing + avatar size + right padding)
    # text_x is 30, inter-padding is 40, right padding is 30
    bg_width = 30 + max_text_width + 40 + avatar_width + 30
    
    # Background height bounds are perfectly balanced dynamically around the text bounds
    card_height = current_y + 30
    
    # Prepare footer watermark showing data snapshot timestamp
    if cache_time:
        ts_str = cache_time.strftime("%Y-%m-%d %H:%M:%S")
        footer_img = make_text(f"Rating data: {ts_str} (UTC+8)", 12, fill=(180, 180, 180))
    else:
        footer_img = make_text("Rating data: N/A", 12, fill=(180, 180, 180))
    footer_gap = 12
    
    bg = BuildImage.new("RGBA", (bg_width, card_height), (247, 247, 247, 255))
    
    # Paste all texts
    for img, x, y in lines_to_draw:
        bg.paste(img, (x, y), alpha=True)
        
    # Draw subtle gray divider
    from PIL import ImageDraw
    draw = ImageDraw.Draw(bg.image)
    draw.line((30, divider_y, 30 + max_text_width, divider_y), fill=(235, 235, 235, 255), width=2)
        
    # Paste Avatar on the right side
    if avatar_img:
        avatar_x = bg_width - avatar_width - 30
        bg.paste(avatar_img, (avatar_x, 30), alpha=True)
    
    # Paste footer timestamp at bottom-left of the card
    footer_y = card_height - footer_img.height - 8
    bg.paste(footer_img, (30, footer_y), alpha=True)
        
    output = io.BytesIO()
    bg.image.save(output, format="PNG")
    return output.getvalue()
