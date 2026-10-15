"""
Overlay Renderer - Dùng Pillow vẽ các frame UI tin tức chuyên nghiệp 9:16 (1080x1920)
Khớp chuẩn xác theo mẫu thực tế của người dùng:
1. Frame 1 (Title Hero):
   - Background toàn màn hình (ảnh bài báo gốc zoompan)
   - Badge Nguồn (top-left, x=95, y=140)
   - Logo góc trên phải: TỰ ĐỘNG chọn logo đỏ khi nền sáng, logo trắng khi nền tối!
   - Vạch dọc màu đỏ (x=120, y=1100, w=16)
   - Tiêu đề chữ trắng in đậm kích thước lớn 68px
   - Ngày đăng góc dưới cùng bên trái (x=108, y=1640)

2. Frame 2 (Chi tiết vụ việc):
   - Background ảnh bài báo làm mờ (heavy blur) + phủ tối cinematic
   - Ảnh chi tiết (inset photo) bo tròn 32px ở vị trí trung tâm phía trên (x=108, y=384, w=864, h=774)
   - Badge Nguồn (top-left) + Badge đỏ "DIỄN BIẾN VỤ VIỆC" ngay phía dưới
   - Logo trắng góc trên bên phải
   - Text nội dung tóm tắt chi tiết cỡ chữ 60px lớn, rõ nét, căn trái thẳng hàng (x=158, y=1230)
   - Ngày đăng ở góc dưới cùng bên trái (x=108, y=1640)

3. Frame 3 (Theo dõi / Outro):
   - Nền đen tuyền tối giản, sang trọng
   - Logo TIN 360 NHANH màu trắng kích thước lớn ở giữa
   - Nút bấm FOLLOW màu xanh nổi bật với biểu tượng bàn tay click
   - Lời kêu gọi: "THEO DÕI ĐỂ XEM THÊM NHIỀU TIN HOT"
"""

import os
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from datetime import datetime

W, H = 1080, 1920

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_INTER = os.path.join(BASE_DIR, "fonts", "Inter-Bold.ttf")
if not os.path.exists(FONT_INTER):
    FONT_INTER = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

LOGO_RED_PATH = os.path.join(BASE_DIR, "assets", "logo_red_clean.png")
LOGO_WHITE_PATH = os.path.join(BASE_DIR, "assets", "logo_white_clean.png")
FOLLOW_FRAME_PATH = os.path.join(BASE_DIR, "assets", "follow_frame_1080.png")


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_INTER, size)
    except Exception:
        return ImageFont.load_default()


def _wrap(text: str, font, max_w: int, draw: ImageDraw.Draw) -> List[str]:
    """Tự động ngắt dòng thông minh theo pixel width thực tế."""
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if draw.textlength(test, font=font) <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines or [text]


def get_current_date_str() -> str:
    """Trả về ngày định dạng DD/MM/YYYY."""
    now = datetime.now()
    return now.strftime("%d/%m/%Y")


def detect_is_light_bg(img_path_or_img, area="top_right") -> bool:
    """Kiểm tra độ sáng trung bình tại vùng đặt logo để quyết định dùng logo đỏ hay trắng."""
    try:
        if isinstance(img_path_or_img, str):
            if not os.path.exists(img_path_or_img):
                return False
            im = Image.open(img_path_or_img).convert("RGB")
        else:
            im = img_path_or_img.convert("RGB")
            
        w, h = im.size
        if area == "top_right":
            crop_box = (int(w * 0.65), int(h * 0.03), int(w * 0.95), int(h * 0.16))
        else:
            crop_box = (0, 0, w, h)
        sample = im.crop(crop_box)
        mean_lum = np.array(sample).mean()
        return mean_lum > 140
    except Exception:
        return False


def _draw_logo(target_img: Image.Image, is_dark_bg: bool = True, target_w: int = 240, top: int = 120, right: int = 90):
    """Vẽ logo góc trên bên phải: logo trắng cho nền tối, logo đỏ cho nền sáng."""
    logo_path = LOGO_WHITE_PATH if is_dark_bg else LOGO_RED_PATH
    if not os.path.exists(logo_path):
        return

    try:
        logo = Image.open(logo_path).convert("RGBA")
        ratio = logo.height / logo.width
        target_h = int(target_w * ratio)
        logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
        x = W - right - target_w
        target_img.alpha_composite(logo, (x, top))
    except Exception as e:
        print(f"Error drawing logo: {e}")


def _draw_source_pill(draw: ImageDraw.Draw, source: str, top: int = 140, left: int = 95):
    """Badge Nguồn bo tròn bán nguyệt nền xám đen mờ chuẩn như mẫu."""
    font = _font(28)
    text = f"Nguồn: {source.lower()}"
    text_w = int(draw.textlength(text, font=font))
    pad_x, pad_y = 24, 14
    box = [(left, top), (left + text_w + pad_x * 2, top + 34 + pad_y * 2)]
    draw.rounded_rectangle(box, radius=18, fill=(0, 0, 0, 160))
    draw.text((left + pad_x, top + pad_y - 2), text, font=font, fill=(240, 240, 240, 255))
    return box[1][1]  # return bottom y


def _draw_headline_pill(draw: ImageDraw.Draw, headline: str, top: int = 215, left: int = 95):
    """Badge đỏ chữ trắng nổi bật (như DIỄN BIẾN VỤ VIỆC)."""
    font = _font(34)
    text = headline.upper().strip()
    text_w = int(draw.textlength(text, font=font))
    pad_x, pad_y = 26, 14
    box = [(left, top), (left + text_w + pad_x * 2, top + 42 + pad_y * 2)]
    draw.rounded_rectangle(box, radius=16, fill=(215, 0, 20, 255))
    draw.text((left + pad_x, top + pad_y), text, font=font, fill=(255, 255, 255, 255))
    return box[1][1]


def _draw_date(draw: ImageDraw.Draw, date_str: str, left: int = 108, bottom: int = 1640):
    """Dòng chữ 'Ngày đăng: dd/mm/yyyy' ở góc dưới trái (vị trí chuẩn mẫu y=1640)."""
    font = _font(28)
    text = f"Ngày đăng: {date_str}"
    draw.text((left, bottom), text, font=font, fill=(220, 220, 220, 220))


# ─────────────────────────────────────────────────────────────────────────────
# 1. FRAME 1: TITLE HERO OVERLAY (Tương tự Hình 1)
# ─────────────────────────────────────────────────────────────────────────────

def make_title_hero_overlay(
    title: str,
    source: str,
    date_str: str,
    bg_image_path: Optional[str],
    out_path: str
):
    """
    Overlay Frame 1 (Tiêu đề bài viết kèm hình):
    - Background ảnh bài báo được ffmpeg zoom phía sau
    - Gradient đen mờ từ nửa dưới để tôn chữ trắng
    - Nguồn góc trên trái, Logo góc trên phải (tự động chọn đỏ/trắng theo độ sáng ảnh)
    - Vạch đỏ dọc bên trái tiêu đề
    - Tiêu đề chữ trắng kích thước lớn 68px
    - Ngày đăng dưới góc trái y=1640
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Tự động chọn logo đỏ trên nền sáng, logo trắng trên nền tối
    is_light = detect_is_light_bg(bg_image_path, "top_right") if bg_image_path else False

    # 1. Gradient tối chuyển tiếp mượt mà từ 40% màn hình xuống đáy
    grad_start = int(H * 0.45)
    for y in range(grad_start, H):
        factor = (y - grad_start) / (H - grad_start)
        alpha = int(min(240, 255 * (factor ** 1.35)))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    # 2. Source badge & Logo
    _draw_source_pill(draw, source, top=140, left=95)
    _draw_logo(img, is_dark_bg=not is_light, target_w=250, top=130, right=90)

    # 3. Tiêu đề bài viết
    font_title = _font(68)
    max_text_w = W - 320  # rộng ~760px
    lines = _wrap(title, font_title, max_text_w, draw)
    lines = lines[:5]

    line_h = 88
    total_h = len(lines) * line_h
    start_y = 1100

    # Vạch đỏ dọc thẳng bên trái tiêu đề (x=120)
    bar_x = 120
    bar_w = 16
    draw.rounded_rectangle(
        [(bar_x, start_y + 8), (bar_x + bar_w, start_y + total_h - 8)],
        radius=6, fill=(220, 18, 28, 255)
    )

    # Vẽ các dòng tiêu đề chữ trắng nổi bật (x=175)
    text_x = 175
    for i, line in enumerate(lines):
        y = start_y + i * line_h
        draw.text((text_x + 2, y + 2), line, font=font_title, fill=(0, 0, 0, 180))
        draw.text((text_x, y), line, font=font_title, fill=(255, 255, 255, 255))

    # 4. Ngày đăng góc dưới cùng
    _draw_date(draw, date_str or get_current_date_str(), left=108, bottom=1640)

    img.save(out_path)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# 2. FRAME 2: DETAIL FRAME BACKGROUND & OVERLAY (Tương tự Hình 2)
# ─────────────────────────────────────────────────────────────────────────────

def create_detail_frame_image(
    article_photo_path: Optional[str],
    headline_badge: str,
    content_text: str,
    source: str,
    date_str: str,
    out_path: str
):
    """
    Tạo frame ảnh chi tiết hoàn chỉnh:
    - Nền: Lấy chính ảnh bài báo blur thật mạnh (Radius 50) + phủ lớp tối màu #0c0c0f (alpha ~ 72%)
    - Ảnh Inset: Bo góc tròn 32px ở vị trí trung tâm phía trên (x=108, y=384, w=864, h=774)
    - Badge Nguồn + Badge đỏ (DIỄN BIẾN VỤ VIỆC)
    - Logo TIN 360 NHANH màu trắng góc trên bên phải
    - Nội dung chữ lớn màu trắng rõ nét phía dưới ảnh (x=158, y=1230, font 60px)
    - Ngày đăng ở góc dưới (x=108, y=1640)
    """
    # 1. Tạo nền canvas tối
    canvas = Image.new("RGBA", (W, H), (18, 18, 22, 255))

    inset_img = None
    if article_photo_path and os.path.exists(article_photo_path):
        try:
            raw_photo = Image.open(article_photo_path).convert("RGB")
            # Scale lấp đầy 1080x1920
            ratio = max(W / raw_photo.width, H / raw_photo.height)
            bg_w, bg_h = int(raw_photo.width * ratio), int(raw_photo.height * ratio)
            bg_scaled = raw_photo.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
            crop_x = (bg_w - W) // 2
            crop_y = (bg_h - H) // 2
            bg_cropped = bg_scaled.crop((crop_x, crop_y, crop_x + W, crop_y + H))
            
            # Làm mờ cinematic
            bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(radius=50))
            canvas.paste(bg_blurred, (0, 0))

            # Phủ lớp tối màu đen/than (alpha 72%) lên nền mờ
            dark_tint = Image.new("RGBA", (W, H), (12, 12, 15, 185))
            canvas.alpha_composite(dark_tint)

            inset_img = raw_photo
        except Exception as e:
            print(f"Error processing background blur: {e}")

    # 2. Vẽ ảnh Inset bo góc ở giữa phía trên (x=108, y=384, w=864, h=774)
    inset_x = 108
    inset_y = 384
    inset_w = 864
    inset_h = 774

    if inset_img:
        scale = max(inset_w / inset_img.width, inset_h / inset_img.height)
        scaled_w = int(inset_img.width * scale)
        scaled_h = int(inset_img.height * scale)
        scaled_inset = inset_img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        
        cx = (scaled_w - inset_w) // 2
        cy = (scaled_h - inset_h) // 2
        cropped_inset = scaled_inset.crop((cx, cy, cx + inset_w, cy + inset_h)).convert("RGBA")

        # Tạo mask bo tròn góc 32px
        mask = Image.new("L", (inset_w, inset_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (inset_w, inset_h)], radius=32, fill=255)

        # Dán ảnh inset có bo góc lên canvas
        canvas.paste(cropped_inset, (inset_x, inset_y), mask)

    draw = ImageDraw.Draw(canvas)

    # 3. Badge nguồn & Badge đỏ
    b1_bot = _draw_source_pill(draw, source, top=140, left=95)
    badge_label = headline_badge or "DIỄN BIẾN VỤ VIỆC"
    _draw_headline_pill(draw, badge_label, top=b1_bot + 16, left=95)

    # 4. Logo trắng góc trên phải (nền chi tiết luôn tối nên dùng logo trắng)
    _draw_logo(canvas, is_dark_bg=True, target_w=250, top=130, right=90)

    # 5. Nội dung tóm tắt chi tiết (cỡ chữ 60px lớn, đậm nét, căn trái x=158)
    font_content = _font(60)
    content_max_w = W - 300  # ~780px
    content_lines = _wrap(content_text, font_content, content_max_w, draw)
    content_lines = content_lines[:5]

    text_start_y = 1230
    line_h = 84

    for i, line in enumerate(content_lines):
        y = text_start_y + i * line_h
        draw.text((160, y + 2), line, font=font_content, fill=(0, 0, 0, 180))
        draw.text((158, y), line, font=font_content, fill=(255, 255, 255, 255))

    # 6. Ngày đăng dưới cùng bên trái (x=108, y=1640)
    _draw_date(draw, date_str or get_current_date_str(), left=108, bottom=1640)

    # Lưu kết quả
    canvas.convert("RGB").save(out_path, "JPEG", quality=95)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# 3. FRAME 3: FOLLOW / OUTRO FRAME (Tương tự Hình 3)
# ─────────────────────────────────────────────────────────────────────────────

def create_follow_frame_image(out_path: str):
    """
    Tạo frame kết nối follow xem thêm nhiều tin hot.
    Sử dụng mẫu chuẩn người dùng cung cấp hoặc vẽ vector chuẩn xác.
    """
    if os.path.exists(FOLLOW_FRAME_PATH):
        try:
            im = Image.open(FOLLOW_FRAME_PATH).convert("RGB")
            im = im.resize((W, H), Image.Resampling.LANCZOS)
            im.save(out_path, "JPEG", quality=95)
            return out_path
        except Exception as e:
            print(f"Error copying follow frame: {e}")

    # Fallback vẽ nền đen
    img = Image.new("RGB", (W, H), (0, 0, 0))
    logo_w = 480
    _draw_logo(img, is_dark_bg=True, target_w=logo_w, top=650, right=(W - logo_w) // 2)

    draw = ImageDraw.Draw(img)
    btn_w, btn_h = 320, 100
    bx1 = (W - btn_w) // 2
    by1 = 880
    draw.rounded_rectangle([(bx1, by1), (bx1 + btn_w, by1 + btn_h)], radius=50, fill=(0, 122, 255))
    font_btn = _font(42)
    draw.text((bx1 + 75, by1 + 25), "FOLLOW", font=font_btn, fill=(255, 255, 255))

    font_cta = _font(34)
    cta1 = "THEO DÕI ĐỂ XEM THÊM"
    cta2 = "NHIỀU TIN HOT"
    draw.text(((W - int(draw.textlength(cta1, font=font_cta))) // 2, 1050), cta1, font=font_cta, fill=(255, 255, 255))
    draw.text(((W - int(draw.textlength(cta2, font=font_cta))) // 2, 1100), cta2, font=font_cta, fill=(255, 255, 255))

    img.save(out_path, "JPEG", quality=95)
    return out_path
