from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple
import os

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/HelveticaNeue.ttc"

def get_font(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

def draw_flowchart_card(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, title: str, subtitle: str = "", icon_text: str = "📦"):
    # Hộp bo tròn màu trắng nổi bật với viền nhẹ
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=20, fill=(255, 255, 255, 255), outline=(226, 232, 240, 255), width=3)
    
    # Icon box màu đen bo tròn
    icon_box_size = 70
    draw.rounded_rectangle([(x + 20, y + (h - icon_box_size)//2), (x + 20 + icon_box_size, y + (h + icon_box_size)//2)], radius=14, fill=(15, 23, 42, 255))
    
    font_icon = get_font(34)
    font_title = get_font(42)
    font_sub = get_font(26)
    
    # Vẽ icon
    draw.text((x + 36, y + (h - icon_box_size)//2 + 14), icon_text, font=font_icon, fill=(255, 255, 255, 255))
    
    # Tiêu đề box
    draw.text((x + 110, y + 25), title, font=font_title, fill=(15, 23, 42, 255))
    
    # Phụ đề nhỏ bên dưới nếu có
    if subtitle:
        draw.text((x + 110, y + 78), subtitle, font=font_sub, fill=(100, 116, 139, 255))

def draw_connecting_arrow(draw: ImageDraw.Draw, x: int, y1: int, y2: int, badge_text: str = ""):
    # Vẽ đường đứt nét hoặc mũi tên nối giữa 2 card
    draw.line([(x, y1), (x, y2)], fill=(71, 85, 105, 255), width=5)
    
    # Đầu mũi tên
    arrow_size = 12
    draw.polygon([(x - arrow_size, y2 - arrow_size), (x + arrow_size, y2 - arrow_size), (x, y2)], fill=(37, 99, 235, 255))
    
    # Badge ở giữa
    if badge_text:
        mid_y = (y1 + y2) // 2
        font_b = get_font(24)
        draw.rounded_rectangle([(x - 70, mid_y - 20), (x + 70, mid_y + 20)], radius=8, fill=(255, 255, 255, 255), outline=(203, 213, 225, 255), width=2)
        draw.text((x - 55, mid_y - 14), badge_text, font=font_b, fill=(30, 41, 59, 255))

def render_infographic_slide(
    bg_image_path: str,
    headline_top: str,
    steps: List[dict],
    source_name: str,
    out_path: str
):
    """
    Vẽ slide biểu đồ diễn giải logic theo kiểu ainius (ảnh 3)
    """
    target_w, target_h = 1080, 1920
    im = Image.new("RGBA", (target_w, target_h), (241, 245, 249, 255))
    
    # Nền mờ phía sau nếu có ảnh
    if bg_image_path and os.path.exists(bg_image_path):
        try:
            bg = Image.open(bg_image_path).convert("RGBA")
            bg = bg.resize((target_w, target_h))
            # Làm mờ và giảm tương phản
            im = Image.blend(im, bg, 0.15)
        except Exception:
            pass

    draw = ImageDraw.Draw(im)
    
    # Badge Header trên cùng
    font_badge = get_font(28)
    hl = headline_top.upper()[:45]
    draw.rounded_rectangle([(40, 50), (target_w - 40, 120)], radius=12, fill=(15, 23, 42, 255))
    draw.text((60, 68), hl, font=font_badge, fill=(255, 255, 255, 255))
    
    # Vẽ các cards
    card_w = 980
    card_h = 140
    start_x = 50
    start_y = 160
    gap = 70
    
    for i, step in enumerate(steps[:4]):
        cy = start_y + i * (card_h + gap)
        draw_flowchart_card(
            draw, start_x, cy, card_w, card_h,
            title=step.get("title", f"Bước {i+1}"),
            subtitle=step.get("subtitle", ""),
            icon_text=step.get("icon", "📌")
        )
        if i < len(steps[:4]) - 1:
            draw_connecting_arrow(draw, target_w // 2, cy + card_h, cy + card_h + gap, step.get("connector", ""))

    im.convert("RGB").save(out_path, quality=95)
