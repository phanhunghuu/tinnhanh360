import os
import subprocess
import requests
import math
from PIL import Image, ImageDraw, ImageFont
from typing import List

FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = "/System/Library/Fonts/HelveticaNeue.ttc"

def get_font(size: int):
    try:
        return ImageFont.truetype(FONT_BOLD, size)
    except Exception:
        return ImageFont.load_default()

def wrap_text_lines(text: str, max_chars: int = 24) -> List[str]:
    words = text.split()
    lines = []
    current_line = []
    current_len = 0
    for w in words:
        if current_len + len(w) + 1 <= max_chars:
            current_line.append(w)
            current_len += len(w) + 1
        else:
            lines.append(" ".join(current_line))
            current_line = [w]
            current_len = len(w)
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def create_base_background(bg_image_path: str, target_w: int = 1080, target_h: int = 1920) -> Image.Image:
    if bg_image_path and os.path.exists(bg_image_path):
        try:
            im = Image.open(bg_image_path).convert("RGBA")
            im_ratio = im.width / im.height
            target_ratio = target_w / target_h
            if im_ratio > target_ratio:
                new_w = int(im.height * target_ratio)
                left = (im.width - new_w) // 2
                im = im.crop((left, 0, left + new_w, im.height))
            else:
                new_h = int(im.width / target_ratio)
                top = (im.height - new_h) // 2
                im = im.crop((0, top, im.width, top + new_h))
            return im.resize((target_w, target_h), Image.Resampling.LANCZOS)
        except Exception:
            pass
    return Image.new("RGBA", (target_w, target_h), (20, 24, 39, 255))

def create_title_hero_overlay(
    bg_image_path: str,
    title_text: str,
    source_name: str,
    out_path: str
):
    """
    Tạo frame tiêu đề cực to, có vạch xanh thẳng đứng như ảnh mẫu 2 của user.
    """
    target_w, target_h = 1080, 1920
    base = create_base_background(bg_image_path, target_w, target_h)
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Nguồn tin ở trên góc trái
    font_src = get_font(28)
    src_label = f"NGUỒN: {source_name.lower()}"
    draw.rounded_rectangle([(50, 60), (50 + len(src_label)*18 + 40, 120)], radius=8, fill=(30, 41, 59, 220))
    draw.text((70, 75), src_label, font=font_src, fill=(255, 255, 255, 255))

    # Gradient đen từ giữa xuống dưới để làm nổi tiêu đề siêu to
    gradient_start = target_h // 2 - 100
    for y in range(gradient_start, target_h):
        progress = (y - gradient_start) / (target_h - gradient_start)
        alpha = int(255 * (progress ** 1.3))
        draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, min(alpha, 255)))

    # Tiêu đề cực to
    font_title = get_font(68)
    lines = wrap_text_lines(title_text, max_chars=18)
    
    # Tính chiều cao khối chữ
    line_h = 85
    total_h = len(lines) * line_h
    start_y = target_h - total_h - 140

    # Vẽ vạch xanh đứng ở bên trái (Accented Blue Bar như trong ảnh)
    draw.rounded_rectangle([(60, start_y + 10), (74, start_y + total_h - 10)], radius=6, fill=(37, 99, 235, 255))

    # Vẽ từng dòng chữ trắng nét dày
    for i, line in enumerate(lines):
        draw.text((100, start_y + i * line_h), line, font=font_title, fill=(255, 255, 255, 255))

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    final_img.save(out_path, quality=95)

def create_karaoke_sentence_frame(
    bg_image_path: str,
    sentence_text: str,
    active_word_index: int, # Từ nào đang đọc tới
    source_name: str,
    headline_top: str,
    out_path: str
):
    """
    Tạo frame phụ đề Karaoke đổi màu từng từ theo câu ngắn gọn.
    """
    target_w, target_h = 1080, 1920
    base = create_base_background(bg_image_path, target_w, target_h)
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Gradient tối phía dưới cho phụ đề
    for y in range(target_h - 400, target_h):
        alpha = int(220 * ((y - (target_h - 400)) / 400))
        draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))

    # Nguồn tin góc trên
    font_src = get_font(26)
    src_label = f"NGUỒN: {source_name.lower()}"
    draw.rounded_rectangle([(50, 50), (50 + len(src_label)*18 + 30, 105)], radius=8, fill=(15, 23, 42, 220))
    draw.text((65, 65), src_label, font=font_src, fill=(255, 255, 255, 255))

    # Tiêu đề trên cùng nhỏ
    if headline_top:
        font_hl = get_font(30)
        draw.rounded_rectangle([(50, 120), (target_w - 50, 185)], radius=8, fill=(15, 23, 42, 220))
        draw.text((70, 135), headline_top.upper()[:40], font=font_hl, fill=(254, 240, 138, 255))

    # Phụ đề Karaoke ở vị trí dưới
    # Tách từ trong câu
    words = sentence_text.split()
    font_sub = get_font(46)
    
    # Chia thành 1 hoặc 2 dòng ngắn gọn
    max_words_per_line = 6
    lines_of_words = []
    for i in range(0, len(words), max_words_per_line):
        lines_of_words.append(words[i:i + max_words_per_line])

    # Hộp chứa phụ đề
    box_y = target_h - 260
    box_h = len(lines_of_words) * 75 + 30
    draw.rounded_rectangle([(40, box_y - 15), (target_w - 40, box_y + box_h)], radius=18, fill=(0, 0, 0, 200), outline=(255, 255, 255, 40), width=2)

    current_idx = 0
    cur_y = box_y
    for line in lines_of_words:
        # Tính chiều dài dòng để căn giữa
        line_w = 0
        word_widths = []
        for w in line:
            w_w = int(draw.textlength(w + " ", font=font_sub))
            word_widths.append(w_w)
            line_w += w_w
            
        cur_x = (target_w - line_w) // 2
        for j, w in enumerate(line):
            # Nếu là từ đang được đọc tới -> Màu vàng sáng (Yellow), ngược lại màu trắng
            if current_idx == active_word_index:
                color = (250, 204, 21, 255) # Vàng nổi bật
            elif current_idx < active_word_index:
                color = (255, 255, 255, 255) # Đã đọc qua
            else:
                color = (156, 163, 175, 230) # Chưa đọc tới (xám mờ)

            draw.text((cur_x, cur_y), w, font=font_sub, fill=color)
            cur_x += word_widths[j]
            current_idx += 1
            
        cur_y += 75

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    final_img.save(out_path, quality=95)

def render_scene_clip_with_motion(
    image_paths: List[str],
    audio_path: str,
    duration: float,
    output_clip_path: str,
    motion_type: str = "zoom_in"
):
    """
    Tạo 1 clip video có hiệu ứng Motion (Zoom In / Zoom Out / Pan) kết hợp âm thanh.
    """
    fps = 24
    num_frames = int(duration * fps)
    
    # Dùng ffmpeg zoompan filter nếu có 1 ảnh nền
    img_path = image_paths[0]
    
    if motion_type == "zoom_in":
        vf = f"zoompan=z='min(zoom+0.0015,1.15)':d={num_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"
    elif motion_type == "zoom_out":
        vf = f"zoompan=z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.0015))':d={num_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"
    else: # pan_left
        vf = f"zoompan=z='1.1':x='if(lte(on,1),(iw-iw/zoom)/2,x-1)':y='ih/2-(ih/zoom/2)':d={num_frames}:s=1080x1920:fps={fps}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_path,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.3f}",
        output_clip_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
