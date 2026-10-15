import os
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont
from typing import List

def download_file(url: str, dest_path: str) -> bool:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception as e:
        print("Download error:", e)
    return False

def wrap_text(text: str, max_chars: int = 24) -> List[str]:
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

def create_styled_scene_frame(
    bg_image_path: str,
    headline: str,
    subtitle_text: str,
    source_name: str,
    out_path: str
):
    """
    Dùng Pillow tạo khung hình chuẩn 1080x1920 với:
    - Ảnh nền căn chuẩn 9:16
    - Thanh nguồn báo ở góc trên
    - Tiêu đề tin nổi bật
    - Phụ đề cháy chữ ở giữa dưới
    """
    target_w, target_h = 1080, 1920
    
    # 1. Mở hoặc tạo ảnh nền
    if bg_image_path and os.path.exists(bg_image_path):
        try:
            im = Image.open(bg_image_path).convert("RGBA")
            # Crop/Scale tỉ lệ 9:16
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
            base = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
        except Exception:
            base = Image.new("RGBA", (target_w, target_h), (17, 24, 39, 255))
    else:
        base = Image.new("RGBA", (target_w, target_h), (17, 24, 39, 255))

    # 2. Tạo layer vẽ hiệu ứng
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Gradient tối ở trên và dưới để làm nổi chữ
    for y in range(250):
        alpha = int(180 * (1 - y / 250))
        draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))
        
    for y in range(target_h - 450, target_h):
        alpha = int(220 * ((y - (target_h - 450)) / 450))
        draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))

    # Font chữ hệ thống macOS
    try:
        font_source = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 36, index=0)
        font_headline = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 48, index=1)
        font_sub = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 44, index=1)
    except Exception:
        font_source = ImageFont.load_default()
        font_headline = font_source
        font_sub = font_source

    # Vẽ huy hiệu Nguồn tin (Góc trên bên trái)
    source_label = f"NGUỒN: {source_name.upper()}"
    draw.rounded_rectangle([(40, 60), (40 + len(source_label)*24 + 40, 130)], radius=12, fill=(220, 38, 38, 230))
    draw.text((60, 75), source_label, font=font_source, fill=(255, 255, 255, 255))

    # Vẽ Tiêu đề phân cảnh (Headline trên khung tin)
    if headline:
        hl_lines = wrap_text(headline.upper(), max_chars=22)
        start_y = 180
        for line in hl_lines:
            draw.text((50, start_y), line, font=font_headline, fill=(254, 240, 138, 255))
            start_y += 60

    # Vẽ phụ đề dạng Subtitle (Dưới cùng)
    if subtitle_text:
        sub_lines = wrap_text(subtitle_text, max_chars=26)
        sub_y = target_h - 320
        # Nền mờ cho phụ đề
        box_h = len(sub_lines) * 60 + 40
        draw.rounded_rectangle([(30, sub_y - 20), (target_w - 30, sub_y + box_h)], radius=16, fill=(0, 0, 0, 180))
        for line in sub_lines:
            # Viền đen bóng mờ
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                draw.text((60 + dx, sub_y + dy), line, font=font_sub, fill=(0, 0, 0, 255))
            draw.text((60, sub_y), line, font=font_sub, fill=(255, 255, 255, 255))
            sub_y += 60

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    final_img.save(out_path, quality=95)

def render_news_video(
    audio_path: str,
    srt_sub_path: str,
    scenes: list,
    article_images: list,
    source_name: str,
    output_mp4_path: str,
    pexels_key: str = None
):
    work_dir = os.path.dirname(output_mp4_path)
    os.makedirs(work_dir, exist_ok=True)

    # 1. Lấy độ dài audio
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    duration = float(subprocess.check_output(probe_cmd).strip())

    # 2. Tải ảnh từ bài báo
    downloaded_images = []
    for idx, img_url in enumerate(article_images[:len(scenes) + 1]):
        dest = os.path.join(work_dir, f"art_raw_{idx}.jpg")
        if download_file(img_url, dest):
            downloaded_images.append(dest)

    # 3. Tạo từng khung hình hoàn chỉnh bằng Pillow
    rendered_frames = []
    num_scenes = max(len(scenes), 1)
    scene_duration = duration / num_scenes

    for idx, scene in enumerate(scenes):
        bg = downloaded_images[idx % len(downloaded_images)] if downloaded_images else None
        frame_path = os.path.join(work_dir, f"scene_frame_{idx}.jpg")
        create_styled_scene_frame(
            bg_image_path=bg,
            headline=scene.get("headline", ""),
            subtitle_text=scene.get("text", ""),
            source_name=source_name,
            out_path=frame_path
        )
        rendered_frames.append(frame_path)

    # 4. Tạo file concat cho FFmpeg
    concat_txt_path = os.path.join(work_dir, "inputs.txt")
    with open(concat_txt_path, "w", encoding="utf-8") as f:
        for fpath in rendered_frames:
            f.write(f"file '{os.path.abspath(fpath)}'\n")
            f.write(f"duration {scene_duration:.2f}\n")
        f.write(f"file '{os.path.abspath(rendered_frames[-1])}'\n")

    # 5. Render video MP4 với FFmpeg (Độc lập không cần thư viện libass)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_txt_path,
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        output_mp4_path
    ]

    print("Render video lệnh:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return output_mp4_path
