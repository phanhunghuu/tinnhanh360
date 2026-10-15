"""
Video Pipeline - Dựng từng scene theo bố cục chính xác:
1. Frame 1 (title_hero): Background ảnh bài báo zoompan liên tục + overlay tiêu đề lớn, vạch đỏ, nguồn, logo (đỏ/trắng tự động), ngày đăng.
2. Các Frame chi tiết (news_detail): Render frame ảnh chi tiết tĩnh (nền mờ + ảnh bài báo inset bo tròn + badge đỏ + text nội dung to + logo trắng + ngày đăng), hoặc áp dụng chuyển động zoompan nhẹ.
3. Frame kết (follow): Nền đen tĩnh + logo TIN 360 NHANH trắng + nút FOLLOW + kêu gọi theo dõi.
"""

import os
import subprocess
import requests
import io
from typing import List, Optional
from PIL import Image

from overlay_renderer import (
    make_title_hero_overlay,
    create_detail_frame_image,
    create_follow_frame_image,
    get_current_date_str,
)


def download_file(url: str, dest: str) -> bool:
    try:
        # Hỗ trợ cả file cục bộ
        if os.path.exists(url):
            img = Image.open(url)
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            if w < 1080 or h < 1080:
                scale = max(1080 / max(w, 1), 1080 / max(h, 1))
                new_w, new_h = int(w * scale), int(h * scale)
                rgb_img = rgb_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            rgb_img.save(dest, "JPEG", quality=95)
            return True

        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content))
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            if w < 1080 or h < 1080:
                scale = max(1080 / max(w, 1), 1080 / max(h, 1))
                new_w, new_h = int(w * scale), int(h * scale)
                rgb_img = rgb_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            rgb_img.save(dest, "JPEG", quality=95)
            return True
    except Exception as e:
        print(f"Download or process image error: {e}")
    return False



def _make_solid_bg(path: str):
    """Tạo ảnh nền tối studio thay thế khi không có ảnh bài báo."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=0x18181c:s=2160x3840:d=1",
        "-frames:v", "1", path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _build_zoompan_filter(motion: str, fps: int, num_frames: int) -> str:
    """
    Tạo ffmpeg zoompan filter cho toàn bộ duration.
    Đảm bảo 9:16 và setsar=1 không biến dạng.
    """
    d = num_frames
    base_prep = "scale='if(gt(a,2160/3840),-2,2160)':'if(gt(a,2160/3840),3840,-2)',crop=2160:3840,setsar=1"

    if motion == "zoom_in":
        return (
            f"{base_prep},"
            f"zoompan=z='min(1+on*0.0008,1.20)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s=1080x1920:fps={fps},"
            f"setsar=1"
        )
    elif motion == "zoom_out":
        return (
            f"{base_prep},"
            f"zoompan=z='max(1.20-on*0.0008,1.0)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s=1080x1920:fps={fps},"
            f"setsar=1"
        )
    elif motion == "pan":
        return (
            f"{base_prep},"
            f"zoompan=z='1.12'"
            f":x='(iw-iw/zoom)/2 + (iw-iw/zoom)*on/{d}/2'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={d}:s=1080x1920:fps={fps},"
            f"setsar=1"
        )
    else:  # static
        return "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"


def render_scene_clip(
    bg_image: str,
    audio_path: str,
    duration: float,
    motion: str,
    overlay_path: Optional[str],
    output_path: str,
    fps: int = 24,
):
    """
    Dựng 1 scene clip:
    - Nếu có overlay_path (như Frame 1): Zoompan bg_image + overlay tĩnh lên trên.
    - Nếu không có overlay_path (bg_image đã là ảnh hoàn chỉnh như Frame 2 hoặc Frame 3): Tạo video tĩnh hoặc zoom cực nhẹ.
    """
    num_frames = int(duration * fps) + 2

    if overlay_path:
        # Trường hợp Frame 1: ảnh nền di chuyển, overlay chữ đứng yên
        zoompan = _build_zoompan_filter(motion, fps, num_frames)
        filter_complex = (
            f"[0:v]{zoompan}[bg];"
            f"[bg][1:v]overlay=0:0,setsar=1[out]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", bg_image,
            "-loop", "1", "-i", overlay_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "2:a",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.4f}",
            output_path
        ]
    else:
        # Trường hợp Frame 2 & Frame 3: ảnh đã render hoàn chỉnh, giữ khung hình 1080x1920 sắc nét
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", bg_image,
            "-i", audio_path,
            "-vf", "scale=1080:1920,setsar=1",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.4f}",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{result.stderr[-1000:]}")

    return output_path


def render_full_video(
    scenes: List[dict],
    source_name: str,
    article_images: List[str],
    tts_results: List[dict],
    work_dir: str,
    final_output_path: str,
    fps: int = 24,
):
    """
    Dựng hoàn chỉnh video từ các scene:
    - Frame 1: Tiêu đề to + vạch đỏ + logo thích ứng (Hình 1)
    - Frame 2, 3...: Chi tiết vụ việc với ảnh inset bo tròn + badge đỏ (Hình 2)
    - Frame Cuối: Follow outro nền đen + nút Follow (Hình 3)
    """
    os.makedirs(work_dir, exist_ok=True)
    date_str = get_current_date_str()

    # Tải TẤT CẢ ảnh bài báo (không giới hạn) - ưu tiên dùng hết hình có trong bài
    bg_images = []
    for idx, url in enumerate(article_images):
        dest = os.path.join(work_dir, f"bg_{idx}.jpg")
        if download_file(url, dest):
            bg_images.append(dest)
        # Giới hạn tối đa 15 hình để tránh quá tải
        if len(bg_images) >= 15:
            break

    if not bg_images:
        default_bg = os.path.join(work_dir, "bg_default.jpg")
        _make_solid_bg(default_bg)
        bg_images.append(default_bg)

    clip_paths = []

    for idx, (scene, tts) in enumerate(zip(scenes, tts_results)):
        sc_type  = scene.get("type", "news_detail")
        motion   = scene.get("motion", "zoom_in")
        headline = scene.get("headline", "")
        text     = scene.get("text", "")
        duration = tts["duration"] + 0.35  # Giữ trọn âm thanh cuối

        clip_out = os.path.join(work_dir, f"clip_{idx:02d}.mp4")
        current_article_photo = bg_images[idx % len(bg_images)]

        if sc_type == "title_hero":
            # FRAME 1 (Hình 1): Ảnh bài báo làm background zoompan, text overlay tĩnh
            ovl_path = os.path.join(work_dir, f"ovl_{idx:02d}_hero.png")
            make_title_hero_overlay(
                title=scene.get("headline", headline),
                source=source_name,
                date_str=date_str,
                bg_image_path=current_article_photo,
                out_path=ovl_path
            )
            render_scene_clip(
                bg_image=current_article_photo,
                audio_path=tts["audio_path"],
                duration=duration,
                motion=motion,
                overlay_path=ovl_path,
                output_path=clip_out,
                fps=fps,
            )

        elif sc_type == "follow":
            # FRAME CUỐI (Hình 3): Nền đen, Logo trắng ở giữa, Nút Follow, Kêu gọi theo dõi
            follow_img_path = os.path.join(work_dir, f"frame_{idx:02d}_follow.jpg")
            create_follow_frame_image(follow_img_path)
            render_scene_clip(
                bg_image=follow_img_path,
                audio_path=tts["audio_path"],
                duration=duration,
                motion="static",
                overlay_path=None,
                output_path=clip_out,
                fps=fps,
            )

        else:
            # CÁC FRAME CHI TIẾT (Hình 2): Nền mờ + Ảnh Inset bo tròn + Badge đỏ + Chữ lớn
            detail_img_path = os.path.join(work_dir, f"frame_{idx:02d}_detail.jpg")
            create_detail_frame_image(
                article_photo_path=current_article_photo,
                headline_badge=headline or "DIỄN BIẾN VỤ VIỆC",
                content_text=text,
                source=source_name,
                date_str=date_str,
                out_path=detail_img_path
            )
            render_scene_clip(
                bg_image=detail_img_path,
                audio_path=tts["audio_path"],
                duration=duration,
                motion="static",
                overlay_path=None,
                output_path=clip_out,
                fps=fps,
            )

        clip_paths.append(clip_out)

    # Concat các clips thành video tổng hợp
    concat_list = os.path.join(work_dir, "final_concat.txt")
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c", "copy",
        final_output_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return final_output_path
