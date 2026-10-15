"""
Overlay Renderer - Dùng Pillow vẽ các frame UI tin tức chuyên nghiệp 9:16 (1080x1920)
Khớp chuẩn xác theo mẫu thực tế và yêu cầu mới:
1. Frame 1 (Title Hero):
   - Background toàn màn hình (ảnh bài báo gốc zoompan)
   - Lớp gradient đen kéo cao lên (từ 35% màn hình) để tiêu đề hiện cực kỳ rõ nét
   - Badge Nguồn (top-left) + Logo đỏ/trắng tự động (top-right)
   - Tiêu đề: Font Inter-Black (trọng số 900 đậm nhất), hiển thị trọn vẹn 100% không cắt cụt
   - Tự động co dãn cỡ chữ thông minh (60-68px) và giảm giãn cách dòng (line_spacing) gọn gàng
   - Vạch dọc màu đỏ (#dc2626) nổi bật
   - Ngày đăng góc dưới cùng bên trái

2. Frame 2 (Chi tiết vụ việc):
   - Background ảnh bài báo làm mờ (heavy blur) + phủ tối cinematic
   - Ảnh chi tiết (inset photo) bo tròn 32px ở vị trí trung tâm phía trên
   - Badge Nguồn (top-left) + Badge đỏ "DIỄN BIẾN VỤ VIỆC"
   - Logo trắng góc trên bên phải
   - Text nội dung tóm tắt chi tiết: Chia theo từng câu, cỡ chữ 48-52px vừa vặn, giảm giãn cách dòng, đọc trọn vẹn
   - Ngày đăng ở góc dưới cùng bên trái

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

# Font Inter-Black (900 đậm nhất) cho tiêu đề và Inter-Bold cho các chi tiết
FONT_INTER_BLACK = os.path.join(BASE_DIR, "fonts", "Inter-Black.ttf")
FONT_INTER_BOLD = os.path.join(BASE_DIR, "fonts", "Inter-Bold.ttf")

if not os.path.exists(FONT_INTER_BLACK):
    FONT_INTER_BLACK = FONT_INTER_BOLD
if not os.path.exists(FONT_INTER_BOLD):
    FONT_INTER_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

LOGO_RED_PATH = os.path.join(BASE_DIR, "assets", "logo_red_clean.png")
LOGO_WHITE_PATH = os.path.join(BASE_DIR, "assets", "logo_white_clean.png")
FOLLOW_FRAME_PATH = os.path.join(BASE_DIR, "assets", "follow_frame_1080.png")


def _font_black(size: int) -> ImageFont.FreeTypeFont:
    """Font Inter-Black (trọng số 900) đậm nhất."""
    try:
        return ImageFont.truetype(FONT_INTER_BLACK, size)
    except Exception:
        try:
            return ImageFont.truetype(FONT_INTER_BOLD, size)
        except Exception:
            return ImageFont.load_default()


def _font_bold(size: int) -> ImageFont.FreeTypeFont:
    """Font Inter-Bold cho badge và văn bản chi tiết."""
    try:
        return ImageFont.truetype(FONT_INTER_BOLD, size)
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
    font = _font_bold(28)
    text = f"Nguồn: {source.lower()}"
    text_w = int(draw.textlength(text, font=font))
    pad_x, pad_y = 24, 14
    box = [(left, top), (left + text_w + pad_x * 2, top + 34 + pad_y * 2)]
    draw.rounded_rectangle(box, radius=18, fill=(0, 0, 0, 160))
    draw.text((left + pad_x, top + pad_y - 2), text, font=font, fill=(240, 240, 240, 255))
    return box[1][1]


def _draw_headline_pill(draw: ImageDraw.Draw, headline: str, top: int = 215, left: int = 95):
    """Badge đỏ chữ trắng nổi bật (như DIỄN BIẾN VỤ VIỆC)."""
    font = _font_bold(34)
    text = headline.upper().strip()
    text_w = int(draw.textlength(text, font=font))
    pad_x, pad_y = 26, 14
    box = [(left, top), (left + text_w + pad_x * 2, top + 42 + pad_y * 2)]
    draw.rounded_rectangle(box, radius=16, fill=(215, 0, 20, 255))
    draw.text((left + pad_x, top + pad_y), text, font=font, fill=(255, 255, 255, 255))
    return box[1][1]


def _draw_date(draw: ImageDraw.Draw, date_str: str, left: int = 108, bottom: int = 1640):
    """Dòng chữ 'Ngày đăng: dd/mm/yyyy' ở góc dưới trái (vị trí chuẩn mẫu y=1640)."""
    font = _font_bold(28)
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
    - Mảng shadow đen được kéo rất cao lên (từ 25% màn hình) để tiêu đề hiện cực kỳ rõ nét.
    - Tiêu đề in đậm nhất (Font Inter-Black 900).
    - Hiển thị trọn vẹn 100% nội dung tiêu đề, không cắt bớt chữ nào.
    - Giảm giãn cách dòng (line_spacing) gọn gàng.
    - Vạch đỏ dọc thẳng hàng bên trái tiêu đề.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Chọn logo đỏ trên nền sáng, logo trắng trên nền tối
    is_light = detect_is_light_bg(bg_image_path, "top_right") if bg_image_path else False

    # 1. Mảng shadow đen kéo rất cao lên (bắt đầu từ 25% màn hình) để che tối nền và tôn rõ chữ
    grad_start = int(H * 0.25)
    for y in range(grad_start, H):
        factor = (y - grad_start) / (H - grad_start)
        alpha = int(min(250, 255 * (factor ** 1.15)))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    # 2. Source badge & Logo
    _draw_source_pill(draw, source, top=140, left=95)
    _draw_logo(img, is_dark_bg=not is_light, target_w=250, top=130, right=90)

    # 3. Tiêu đề bài viết: Dùng Inter-Black (900), tự động điều chỉnh cỡ chữ nếu tiêu đề dài
    font_size = 64
    font_title = _font_black(font_size)
    max_text_w = W - 300  # Rộng ~780px
    lines = _wrap(title, font_title, max_text_w, draw)

    # Nếu tiêu đề dài hơn 4 dòng, tự động giảm nhẹ cỡ chữ để đảm bảo hiển thị trọn vẹn và đẹp mắt
    if len(lines) > 4:
        font_size = 56
        font_title = _font_black(font_size)
        lines = _wrap(title, font_title, max_text_w, draw)

    # Giảm giãn cách dòng: khoảng cách dòng chỉ bằng font_size + 14px (gọn gàng, chặt chẽ)
    line_h = font_size + 14
    total_h = len(lines) * line_h

    # Đặt vị trí tiêu đề sao cho vừa vặn trước phần Ngày đăng
    # Đáy tiêu đề cách ngày đăng (1640) khoảng 60px
    start_y = min(1120, 1580 - total_h)

    # Vạch đỏ dọc thẳng bên trái tiêu đề (x=120)
    bar_x = 120
    bar_w = 16
    draw.rounded_rectangle(
        [(bar_x, start_y + 4), (bar_x + bar_w, start_y + total_h - 4)],
        radius=6, fill=(220, 18, 28, 255)
    )

    # Vẽ các dòng tiêu đề chữ trắng nét siêu đậm Inter-Black
    text_x = 175
    for i, line in enumerate(lines):
        y = start_y + i * line_h
        # Shadow đen mạnh hơn để nổi bật chữ trên mọi bức ảnh nền
        draw.text((text_x + 3, y + 3), line, font=font_title, fill=(0, 0, 0, 220))
        draw.text((text_x, y), line, font=font_title, fill=(255, 255, 255, 255))

    # 4. Ngày đăng góc dưới cùng (y=1640)
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
    Tạo frame ảnh chi tiết:
    - Ảnh Inset: Bo góc tròn 32px ở vị trí trung tâm phía trên.
    - Badge Nguồn + Badge đỏ "DIỄN BIẾN VỤ VIỆC".
    - Logo trắng góc trên bên phải.
    - Text nội dung tóm tắt: Font 48-52px, giảm giãn cách dòng, hiển thị đầy đủ câu theo voice.
    - Ngày đăng ở góc dưới (y=1640).
    """
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

            # Phủ lớp tối màu than (alpha 72%) lên nền mờ
            dark_tint = Image.new("RGBA", (W, H), (12, 12, 15, 185))
            canvas.alpha_composite(dark_tint)

            inset_img = raw_photo
        except Exception as e:
            print(f"Error processing background blur: {e}")

    # Vẽ ảnh Inset bo góc ở giữa phía trên (x=108, y=384, w=864, h=774)
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

        # Mask bo tròn góc 32px
        mask = Image.new("L", (inset_w, inset_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (inset_w, inset_h)], radius=32, fill=255)

        canvas.paste(cropped_inset, (inset_x, inset_y), mask)

    draw = ImageDraw.Draw(canvas)

    # Badge nguồn & Badge đỏ
    b1_bot = _draw_source_pill(draw, source, top=140, left=95)
    badge_label = headline_badge or "DIỄN BIẾN VỤ VIỆC"
    _draw_headline_pill(draw, badge_label, top=b1_bot + 16, left=95)

    # Logo trắng góc trên phải
    _draw_logo(canvas, is_dark_bg=True, target_w=250, top=130, right=90)

    # Nội dung tóm tắt chi tiết: tự động co font để vừa màn hình
    # Thứ tự thử: 52 → 46 → 40 → 34px, đảm bảo không đè vào Ngày đăng (y=1640)
    text_start_y = 1220
    max_text_bottom = 1620  # Giữ khoảng trống 20px trước ngày đăng

    for font_size in [52, 46, 40, 34]:
        font_content = _font_bold(font_size)
        content_max_w = W - 260  # Rộng ~820px
        content_lines = _wrap(content_text, font_content, content_max_w, draw)
        line_h = font_size + 14  # Giãn cách dòng tối giản
        total_text_h = len(content_lines) * line_h
        if text_start_y + total_text_h <= max_text_bottom:
            break  # Vừa vặn, dùng font size này

    for i, line in enumerate(content_lines):
        y = text_start_y + i * line_h
        # Dừng vẽ nếu chạm mốc cuối
        if y + line_h > max_text_bottom:
            break
        draw.text((150, y + 2), line, font=font_content, fill=(0, 0, 0, 180))
        draw.text((148, y), line, font=font_content, fill=(255, 255, 255, 255))

    # Ngày đăng dưới cùng bên trái (x=108, y=1640)
    _draw_date(draw, date_str or get_current_date_str(), left=108, bottom=1640)

    canvas.convert("RGB").save(out_path, "JPEG", quality=95)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# 3. FRAME 3: FOLLOW / OUTRO FRAME (Tương tự Hình 3)
# ─────────────────────────────────────────────────────────────────────────────

def create_follow_frame_image(out_path: str):
    """
    Tạo frame kết nối follow xem thêm nhiều tin hot.
    """
    if os.path.exists(FOLLOW_FRAME_PATH):
        try:
            im = Image.open(FOLLOW_FRAME_PATH).convert("RGB")
            im = im.resize((W, H), Image.Resampling.LANCZOS)
            im.save(out_path, "JPEG", quality=95)
            return out_path
        except Exception as e:
            print(f"Error copying follow frame: {e}")

    img = Image.new("RGB", (W, H), (0, 0, 0))
    logo_w = 480
    _draw_logo(img, is_dark_bg=True, target_w=logo_w, top=650, right=(W - logo_w) // 2)

    draw = ImageDraw.Draw(img)
    btn_w, btn_h = 320, 100
    bx1 = (W - btn_w) // 2
    by1 = 880
    draw.rounded_rectangle([(bx1, by1), (bx1 + btn_w, by1 + btn_h)], radius=50, fill=(0, 122, 255))
    font_btn = _font_bold(42)
    draw.text((bx1 + 75, by1 + 25), "FOLLOW", font=font_btn, fill=(255, 255, 255))

    font_cta = _font_bold(34)
    cta1 = "THEO DÕI ĐỂ XEM THÊM"
    cta2 = "NHIỀU TIN HOT"
    draw.text(((W - int(draw.textlength(cta1, font=font_cta))) // 2, 1050), cta1, font=font_cta, fill=(255, 255, 255))
    draw.text(((W - int(draw.textlength(cta2, font=font_cta))) // 2, 1100), cta2, font=font_cta, fill=(255, 255, 255))

    img.save(out_path, "JPEG", quality=95)
    return out_path
