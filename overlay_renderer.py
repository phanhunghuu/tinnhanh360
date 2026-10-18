"""
Overlay Renderer - Dùng Pillow vẽ các frame UI tin tức chuyên nghiệp 9:16 (1080x1920)

KIẾN TRÚC MỚI: Ảnh bài báo được đặt trong KHUNG BO TRÒN (inset frame) giống nhau
cho tất cả các frame. Hiệu ứng zoom/pan chạy BÊN TRONG khung - khung đứng yên.

Cách hoạt động:
- Overlay renderer tạo ảnh PNG (RGBA) có "lỗ trống" bo tròn tại vị trí inset.
  Lỗ trống = alpha = 0 (trong suốt hoàn toàn).
- FFmpeg zoompan ảnh gốc tại đúng vị trí inset, rồi overlay PNG đè lên trên.
- Ảnh chỉ hiện qua "lỗ trống" → tạo hiệu ứng zoom/pan trong khung.

1. Frame 1 (Title Hero):
   - Nền mờ cinematic + phủ tối
   - Badge Nguồn (top-left) + Logo tự động (top-right)
   - Khung ảnh bo tròn 32px (lỗ trống cho zoompan)
   - Tiêu đề Inter-Black 900 + vạch đỏ + ngày đăng ở dưới

2. Frame 2 (Chi tiết):
   - Nền mờ cinematic + phủ tối
   - Badge Nguồn + Badge đỏ headline + Logo trắng
   - Khung ảnh bo tròn 32px (lỗ trống cho zoompan)
   - Subtitle auto-scale + ngày đăng

3. Frame 3 (Follow/Outro): Không đổi - nền đen + logo + nút Follow
"""

import os
from typing import List, Optional, Dict
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

# ── Vị trí inset frame (khung ảnh) ──
# Frame 1 (Title Hero): Khung ảnh ở trên (y=300, h=660), tiêu đề to ở dưới
HERO_INSET = {"x": 108, "y": 300, "w": 864, "h": 660, "radius": 32}

# Frame 2+ (Detail): Khung ảnh ở giữa (y=490, h=670), tiêu đề ở trên, phụ đề ở dưới
DETAIL_INSET = {"x": 108, "y": 490, "w": 864, "h": 670, "radius": 32}


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


def _draw_top_title(draw: ImageDraw.Draw, title: str, start_y: int = 250, max_bottom: int = 470):
    """
    Vẽ tiêu đề chính NẰM PHÍA TRÊN KHUNG ẢNH kèm vạch đỏ dọc bên trái đúng như mẫu.
    Đảm bảo xuất hiện đồng nhất trên cả Frame Title và tất cả Frame Detail.
    """
    max_text_w = W - 280
    for font_size in [52, 46, 40, 36]:
        font_title = _font_black(font_size)
        lines = _wrap(title, font_title, max_text_w, draw)
        line_h = font_size + 12
        total_h = len(lines) * line_h
        if start_y + total_h <= max_bottom:
            break

    # Vạch đỏ dọc bên trái tiêu đề
    bar_x = 108
    bar_w = 12
    draw.rounded_rectangle(
        [(bar_x, start_y + 2), (bar_x + bar_w, start_y + total_h - 2)],
        radius=5, fill=(220, 18, 28, 255)
    )

    # Vẽ chữ tiêu đề
    text_x = 148
    for i, line in enumerate(lines):
        y = start_y + i * line_h
        if y + line_h > max_bottom + 10:
            break
        draw.text((text_x + 2, y + 2), line, font=font_title, fill=(0, 0, 0, 200))
        draw.text((text_x, y), line, font=font_title, fill=(255, 255, 255, 255))

    return start_y + total_h


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
    """Dòng chữ 'Ngày đăng: dd/mm/yyyy' ở góc dưới trái."""
    font = _font_bold(28)
    text = f"Ngày đăng: {date_str}"
    draw.text((left, bottom), text, font=font, fill=(220, 220, 220, 220))


def _make_blurred_bg(canvas: Image.Image, photo_path: str):
    """Tạo nền mờ cinematic từ ảnh bài báo + phủ tối."""
    try:
        raw = Image.open(photo_path).convert("RGB")
        ratio = max(W / raw.width, H / raw.height)
        bg_w = int(raw.width * ratio)
        bg_h = int(raw.height * ratio)
        bg_scaled = raw.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
        cx = (bg_w - W) // 2
        cy = (bg_h - H) // 2
        bg_cropped = bg_scaled.crop((cx, cy, cx + W, cy + H))
        bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(radius=55))
        canvas.paste(bg_blurred, (0, 0))

        # Phủ lớp tối cinematic (alpha ~75%)
        dark_tint = Image.new("RGBA", (W, H), (10, 10, 14, 192))
        canvas.alpha_composite(dark_tint)
    except Exception as e:
        print(f"Error creating blurred bg: {e}")


def _draw_inset_border(draw: ImageDraw.Draw, inset: dict):
    """Vẽ viền mỏng sáng xung quanh khung ảnh inset để tạo cảm giác sắc nét, sang trọng."""
    x, y, w, h, r = inset["x"], inset["y"], inset["w"], inset["h"], inset["radius"]
    # Viền ngoài mỏng màu trắng nhẹ 2px
    draw.rounded_rectangle(
        [(x - 2, y - 2), (x + w + 2, y + h + 2)],
        radius=r + 2,
        outline=(255, 255, 255, 75),
        width=2,
    )


def _cut_inset_hole(img: Image.Image, inset: dict) -> Image.Image:
    """Cắt lỗ trống bo tròn (transparent) tại vị trí inset để ảnh zoompan hiện qua."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    x, y, w, h, r = inset["x"], inset["y"], inset["w"], inset["h"], inset["radius"]

    # Lấy alpha channel hiện tại
    r_ch, g_ch, b_ch, a_ch = img.split()

    # Vẽ hình chữ nhật bo tròn = 0 (trong suốt) lên alpha channel
    a_draw = ImageDraw.Draw(a_ch)
    a_draw.rounded_rectangle(
        [(x, y), (x + w, y + h)],
        radius=r, fill=0
    )

    # Ghép lại
    img = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
    return img


# ─────────────────────────────────────────────────────────────────────────────
# 1. FRAME 1: TITLE HERO (Ảnh trong khung bo tròn ở trên + tiêu đề phía dưới)
# ─────────────────────────────────────────────────────────────────────────────

def make_title_hero_overlay(
    title: str,
    source: str,
    date_str: str,
    bg_image_path: Optional[str],
    out_path: str
) -> Dict:
    """
    Tạo Frame 1 (Title Hero) - overlay PNG có lỗ trống bo tròn cho zoompan (giữ nguyên gốc).

    Layout:
    - Nền mờ cinematic + phủ tối
    - Badge Nguồn (top-left) + Logo (top-right)
    - Khung ảnh bo tròn 32px tại HERO_INSET (y=300, h=660)
    - Gradient đen + Tiêu đề Inter-Black 900 to rõ ở dưới + Vạch đỏ + Ngày đăng

    Returns: {"overlay_path": str, "inset": dict}
    """
    inset = HERO_INSET.copy()
    canvas = Image.new("RGBA", (W, H), (18, 18, 22, 255))

    # 1. Nền mờ cinematic từ ảnh bài báo
    if bg_image_path and os.path.exists(bg_image_path):
        _make_blurred_bg(canvas, bg_image_path)

    draw = ImageDraw.Draw(canvas)

    # 2. Viền khung ảnh (vẽ TRƯỚC khi cắt lỗ trống)
    _draw_inset_border(draw, inset)

    # 3. Logo + Source badge
    _draw_logo(canvas, is_dark_bg=True, target_w=250, top=100, right=80)
    draw = ImageDraw.Draw(canvas)  # refresh sau alpha_composite
    _draw_source_pill(draw, source, top=110, left=80)

    # 4. Gradient đen mờ dần từ dưới lên (0% ở đáy khung ảnh -> 100% ở đáy màn hình)
    grad_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(grad_layer)
    grad_start = inset["y"] + inset["h"]  # Bắt đầu ngay tại đáy khung ảnh
    for y_pos in range(grad_start, H):
        factor = (y_pos - grad_start) / (H - grad_start)
        alpha = int(255 * (factor ** 0.85))
        g_draw.line([(0, y_pos), (W, y_pos)], fill=(0, 0, 0, alpha))
    canvas.alpha_composite(grad_layer)
    draw = ImageDraw.Draw(canvas)

    # 5. Tiêu đề Inter-Black 900 ở dưới khung ảnh
    font_size = 62
    font_title = _font_black(font_size)
    max_text_w = W - 280
    lines = _wrap(title, font_title, max_text_w, draw)

    # Co chữ nếu quá dài
    if len(lines) > 5:
        font_size = 52
        font_title = _font_black(font_size)
        lines = _wrap(title, font_title, max_text_w, draw)
    elif len(lines) > 4:
        font_size = 56
        font_title = _font_black(font_size)
        lines = _wrap(title, font_title, max_text_w, draw)

    line_h = font_size + 14
    total_h = len(lines) * line_h

    # Vị trí tiêu đề: dưới khung ảnh, trên ngày đăng
    inset_bottom = inset["y"] + inset["h"]
    title_area_top = inset_bottom + 50
    title_area_bottom = 1680
    available = title_area_bottom - title_area_top
    if total_h < available:
        start_y = title_area_top + (available - total_h) // 3
    else:
        start_y = title_area_top

    # Vạch đỏ dọc bên trái tiêu đề
    bar_x = 108
    bar_w = 14
    draw.rounded_rectangle(
        [(bar_x, start_y + 4), (bar_x + bar_w, start_y + total_h - 4)],
        radius=6, fill=(220, 18, 28, 255)
    )

    # Vẽ tiêu đề
    text_x = 155
    for i, line in enumerate(lines):
        y = start_y + i * line_h
        draw.text((text_x + 3, y + 3), line, font=font_title, fill=(0, 0, 0, 200))
        draw.text((text_x, y), line, font=font_title, fill=(255, 255, 255, 255))

    # 6. Ngày đăng ở đáy
    _draw_date(draw, date_str or get_current_date_str(), left=108, bottom=1720)

    # 7. Cắt lỗ trống bo tròn tại inset (ảnh zoompan sẽ hiện qua đây)
    canvas = _cut_inset_hole(canvas, inset)

    canvas.save(out_path, "PNG")
    return {"overlay_path": out_path, "inset": inset}


# ─────────────────────────────────────────────────────────────────────────────
# 2. FRAME 2: DETAIL FRAME (Tiêu đề trên + Khung ảnh giữa + Subtitle dưới)
# ─────────────────────────────────────────────────────────────────────────────

def create_detail_frame_image(
    article_photo_path: Optional[str],
    headline_badge: str,
    content_text: str,
    source: str,
    date_str: str,
    out_path: str,
    article_title: str = ""
) -> Dict:
    """
    Tạo frame chi tiết chuẩn như hình mẫu:
    - Top: Badge Nguồn + Badge đỏ DIỄN BIẾN + Logo
    - TRÊN ẢNH: Tiêu đề bài báo luôn hiển thị cố định + vạch đỏ (giúp mọi frame đều có tiêu đề)
    - GIỮA: Khung ảnh bo tròn
    - DƯỚI ẢNH: Subtitle lời đọc MC (auto-scale)
    - ĐÁY: Ngày đăng ở góc dưới thấp (1780)
    """
    inset = DETAIL_INSET.copy()
    canvas = Image.new("RGBA", (W, H), (18, 18, 22, 255))

    # 1. Nền mờ cinematic
    if article_photo_path and os.path.exists(article_photo_path):
        _make_blurred_bg(canvas, article_photo_path)

    draw = ImageDraw.Draw(canvas)

    # 2. Viền khung ảnh
    _draw_inset_border(draw, inset)

    # 3. Badges + Logo
    b1_bot = _draw_source_pill(draw, source, top=85, left=80)
    badge_label = headline_badge or "DIỄN BIẾN VỤ VIỆC"
    _draw_headline_pill(draw, badge_label, top=b1_bot + 10, left=80)
    _draw_logo(canvas, is_dark_bg=True, target_w=240, top=85, right=80)
    draw = ImageDraw.Draw(canvas)

    # 4. TIÊU ĐỀ BÀI BÁO NẰM TRÊN KHUNG ẢNH (Ghim cố định như hình mẫu)
    if article_title:
        _draw_top_title(draw, article_title, start_y=255, max_bottom=inset["y"] - 18)

    # 5. Subtitle text nằm PHÍA DƯỚI KHUNG ẢNH
    inset_bottom = inset["y"] + inset["h"]
    text_start_y = inset_bottom + 45
    max_text_bottom = 1720

    for font_size in [50, 44, 38, 32]:
        font_content = _font_bold(font_size)
        content_max_w = W - 240
        content_lines = _wrap(content_text, font_content, content_max_w, draw)
        line_h = font_size + 14
        total_text_h = len(content_lines) * line_h
        if text_start_y + total_text_h <= max_text_bottom:
            break

    for i, line in enumerate(content_lines):
        y = text_start_y + i * line_h
        if y + line_h > max_text_bottom:
            break
        draw.text((120, y + 2), line, font=font_content, fill=(0, 0, 0, 180))
        draw.text((118, y), line, font=font_content, fill=(255, 255, 255, 255))

    # 6. Dời ngày đăng xuống góc dưới thấp
    _draw_date(draw, date_str or get_current_date_str(), left=108, bottom=1780)

    # 7. Cắt lỗ trống bo tròn
    canvas = _cut_inset_hole(canvas, inset)

    canvas.save(out_path, "PNG")
    return {"overlay_path": out_path, "inset": inset}


# ─────────────────────────────────────────────────────────────────────────────
# 3. FRAME 3: FOLLOW / OUTRO FRAME (Không đổi)
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
