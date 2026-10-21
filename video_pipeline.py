"""
Video Pipeline - Dựng video tin tức với hiệu ứng zoom/pan BÊN TRONG khung ảnh bo tròn.

KIẾN TRÚC:
- Overlay renderer tạo PNG (RGBA) có "lỗ trống" bo tròn tại vị trí inset.
- FFmpeg zoompan ảnh gốc tại kích thước inset, pad ra 1080x1920 tại đúng vị trí.
- Overlay PNG đè lên trên → ảnh chỉ hiện qua lỗ trống = zoom/pan trong khung.

Các loại frame:
1. title_hero: Zoompan trong khung + overlay title
2. news_detail: Zoompan trong khung + overlay subtitle
3. follow: Static (không có khung ảnh)
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
        # Hỗ trợ cả file cục bộ hoặc đường dẫn /outputs/...
        local_path = url
        if url.startswith("/outputs/"):
            local_path = os.path.join(os.path.dirname(__file__), "outputs", url[9:])

        if os.path.exists(local_path):
            img = Image.open(local_path)
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


def _build_inset_zoompan_filter(motion: str, fps: int, num_frames: int, out_w: int, out_h: int) -> str:
    """
    Tạo FFmpeg filter: zoompan ảnh gốc → output tại kích thước khung inset.
    Ảnh được scale 2x lớn hơn inset để có headroom cho zoom/pan.
    """
    d = num_frames
    prep_w = out_w * 2
    prep_h = out_h * 2

    # Scale ảnh lấp đầy prep size (cover), rồi crop chính xác
    base_prep = (
        f"scale={prep_w}:{prep_h}:force_original_aspect_ratio=increase,"
        f"crop={prep_w}:{prep_h},setsar=1"
    )

    if motion == "zoom_in":
        return (
            f"{base_prep},"
            f"zoompan=z='min(1+on*0.0006,1.15)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={fps}"
        )
    elif motion == "zoom_out":
        return (
            f"{base_prep},"
            f"zoompan=z='max(1.15-on*0.0006,1.0)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={fps}"
        )
    elif motion == "pan":
        return (
            f"{base_prep},"
            f"zoompan=z='1.08'"
            f":x='(iw-iw/zoom)/2 + (iw-iw/zoom)*on/{d}/3'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={fps}"
        )
    else:  # static
        return (
            f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )


def render_scene_clip(
    photo_path: str,
    audio_path: str,
    duration: float,
    motion: str,
    overlay_path: Optional[str],
    output_path: str,
    inset: Optional[dict] = None,
    fps: int = 24,
    is_last_scene: bool = False,
    voice_volume: float = 1.0,
):
    """
    Dựng 1 scene clip:
    - Nếu có overlay_path + inset: Zoompan ảnh BÊN TRONG khung bo tròn.
    - Nếu không có overlay_path: Video tĩnh từ ảnh đã render (Follow frame).
    - Nếu is_last_scene=True: Áp dụng hiệu ứng fade out (hình ảnh tối dần về màu đen ở 1 giây cuối).
    """
    num_frames = int(duration * fps) + 2
    voice_gain = max(0.0, min(3.0, float(voice_volume)))
    audio_filter = f"volume={voice_gain:.2f},alimiter=limit=0.95"

    # Tính điểm bắt đầu fade out hình ảnh nếu là frame cuối
    v_fade = ""
    if is_last_scene:
        fade_dur = min(1.0, duration / 2.0)
        st = max(0.0, duration - fade_dur)
        v_fade = f",fade=t=out:st={st:.2f}:d={fade_dur:.2f}"

    if overlay_path and inset:
        # ── ZOOMPAN TRONG KHUNG INSET ──
        ix = inset["x"]
        iy = inset["y"]
        iw = inset["w"]
        ih = inset["h"]

        zoompan = _build_inset_zoompan_filter(motion, fps, num_frames, iw, ih)

        # Scale xuống chuẩn 720x1280 để tiết kiệm 60% RAM, tránh crash trên Cloud Free
        filter_complex = (
            f"[0:v]{zoompan}[zpan];"
            f"[zpan]pad=1080:1920:{ix}:{iy}:color=black[photo];"
            f"[photo][1:v]overlay=0:0:format=auto,scale=720:1280,setsar=1{v_fade}[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-threads", "1",
            "-loop", "1", "-i", photo_path,       # Ảnh gốc bài báo
            "-loop", "1", "-i", overlay_path,      # Overlay PNG (RGBA, lỗ trống)
            "-i", audio_path,                      # Audio
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "2:a",
            "-filter:a", audio_filter,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-max_muxing_queue_size", "1024",
            "-t", f"{duration:.4f}",
            output_path
        ]
    else:
        # ── FRAME TĨNH (Follow, hoặc fallback) ──
        filter_str = f"scale=720:1280,setsar=1{v_fade}"
        cmd = [
            "ffmpeg", "-y",
            "-threads", "1",
            "-loop", "1", "-i", photo_path,
            "-i", audio_path,
            "-vf", filter_str,
            "-map", "0:v", "-map", "1:a",
            "-filter:a", audio_filter,
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-max_muxing_queue_size", "1024",
            "-t", f"{duration:.4f}",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{result.stderr[-1500:]}")

    return output_path


def render_full_video(
    scenes: List[dict],
    source_name: str,
    article_images: List[str],
    tts_results: List[dict],
    work_dir: str,
    final_output_path: str,
    fps: int = 24,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.15,
    voice_volume: float = 1.0,
    progress_callback: Optional[callable] = None,
):
    """
    Dựng hoàn chỉnh video từ các scene:
    - Frame 1: Tiêu đề + ảnh trong khung bo tròn (zoompan trong khung)
    - Frame 2, 3...: Chi tiết + ảnh trong khung bo tròn (zoompan trong khung)
    - Frame Cuối: Follow outro tĩnh
    - Hỗ trợ mix nhạc nền BGM lặp vô tận với volume tùy chỉnh
    """
    os.makedirs(work_dir, exist_ok=True)
    date_str = get_current_date_str()

    # Tải TẤT CẢ ảnh bài báo - dùng hết hình có trong bài, hoán đổi cho các frame
    bg_images = []
    for idx, url in enumerate(article_images):
        dest = os.path.join(work_dir, f"bg_{idx}.jpg")
        if download_file(url, dest):
            bg_images.append(dest)
        if len(bg_images) >= 15:
            break

    if not bg_images:
        default_bg = os.path.join(work_dir, "bg_default.jpg")
        _make_solid_bg(default_bg)
        bg_images.append(default_bg)

    # Lấy tiêu đề chính của bài báo từ scene đầu tiên (title_hero)
    article_title = ""
    for sc in scenes:
        if sc.get("type") == "title_hero":
            article_title = sc.get("headline") or sc.get("text", "")
            break
    if not article_title and scenes:
        article_title = scenes[0].get("headline") or scenes[0].get("text", "")

    clip_paths = []
    # Danh sách hiệu ứng phong phú để hoán đổi nếu dùng lại 1 ảnh
    motion_cycle = ["zoom_in", "pan", "zoom_out"]

    for idx, (scene, tts) in enumerate(zip(scenes, tts_results)):
        sc_type  = scene.get("type", "news_detail")
        # Luân phiên hiệu ứng để dù bài chỉ có 1 ảnh thì mỗi cảnh vẫn chuyển động khác nhau
        motion   = scene.get("motion") or motion_cycle[idx % len(motion_cycle)]
        if len(bg_images) == 1 and sc_type != "title_hero":
            motion = motion_cycle[idx % len(motion_cycle)]

        headline = scene.get("headline", "")
        text     = scene.get("text", "")
        # Khớp chính xác thời lượng audio để frame chuyển ngay khi voice vừa đọc xong câu
        duration = tts["duration"]

        clip_out = os.path.join(work_dir, f"clip_{idx:02d}.mp4")

        # Cho phép người dùng chỉ định ảnh cụ thể cho từng scene (bằng url hoặc số index)
        custom_img_url = scene.get("image_url")
        if custom_img_url:
            custom_dest = os.path.join(work_dir, f"scene_{idx:02d}_custom.jpg")
            if download_file(custom_img_url, custom_dest):
                current_photo = custom_dest
            else:
                current_photo = bg_images[idx % len(bg_images)]
        elif "image_index" in scene and 0 <= int(scene["image_index"]) < len(bg_images):
            current_photo = bg_images[int(scene["image_index"])]
        else:
            current_photo = bg_images[idx % len(bg_images)]

        if sc_type == "title_hero":
            # FRAME 1: Overlay PNG (có lỗ trống) + zoompan trong khung
            ovl_path = os.path.join(work_dir, f"ovl_{idx:02d}_hero.png")
            result = make_title_hero_overlay(
                title=scene.get("headline", headline),
                source=source_name,
                date_str=date_str,
                bg_image_path=current_photo,
                out_path=ovl_path
            )
            render_scene_clip(
                photo_path=current_photo,
                audio_path=tts["audio_path"],
                duration=duration,
                motion=motion,
                overlay_path=result["overlay_path"],
                output_path=clip_out,
                inset=result["inset"],
                fps=fps,
                voice_volume=voice_volume,
            )

        elif sc_type == "follow":
            # FRAME CUỐI: Tĩnh, không có khung ảnh + hiệu ứng fade out tối dần ở cuối
            follow_img_path = os.path.join(work_dir, f"frame_{idx:02d}_follow.jpg")
            create_follow_frame_image(follow_img_path)
            render_scene_clip(
                photo_path=follow_img_path,
                audio_path=tts["audio_path"],
                duration=duration,
                motion="static",
                overlay_path=None,
                output_path=clip_out,
                inset=None,
                fps=fps,
                voice_volume=voice_volume,
                is_last_scene=(idx == len(scenes) - 1),
            )

        else:
            # FRAME CHI TIẾT: Overlay PNG (có lỗ trống) + zoompan trong khung
            ovl_path = os.path.join(work_dir, f"ovl_{idx:02d}_detail.png")
            result = create_detail_frame_image(
                article_photo_path=current_photo,
                headline_badge=headline or "DIỄN BIẾN VỤ VIỆC",
                content_text=text,
                source=source_name,
                date_str=date_str,
                out_path=ovl_path,
                article_title=article_title
            )
            render_scene_clip(
                photo_path=current_photo,
                audio_path=tts["audio_path"],
                duration=duration,
                motion=motion,
                overlay_path=result["overlay_path"],
                output_path=clip_out,
                inset=result["inset"],
                fps=fps,
                voice_volume=voice_volume,
                is_last_scene=(idx == len(scenes) - 1),
            )

        clip_paths.append(clip_out)
        import gc
        gc.collect()

        if progress_callback:
            progress_callback(
                "render_clip",
                f"Đã render xong cảnh {idx + 1}/{len(scenes)}: {headline or sc_type}",
                (idx + 1) / len(scenes)
            )

    # Concat các clips thành video tổng hợp
    if progress_callback:
        progress_callback("merge", "Đang ghép nối các cảnh video...", 0.90)

    concat_list = os.path.join(work_dir, "final_concat.txt")
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    raw_concat_video = os.path.join(work_dir, "concat_temp.mp4") if (bgm_path and os.path.exists(bgm_path)) else final_output_path

    # Concat clips: copy video, re-encode audio để đảm bảo toàn bộ clip cùng sample-rate 44100Hz stereo
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "copy",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        raw_concat_video
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Nếu có nhạc nền BGM -> Mix nhạc nền vào video với âm lượng bgm_volume VÀ FADE OUT KHÚC CUỐI
    if bgm_path and os.path.exists(bgm_path):
        if progress_callback:
            progress_callback("bgm", "Đang lồng nhạc nền và xử lý hiệu ứng âm thanh fade out...", 0.95)
        vol = max(0.01, min(1.0, float(bgm_volume)))
        # Đo tổng thời lượng video để tính điểm bắt đầu fade out
        try:
            probe_out = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", raw_concat_video
            ]).strip()
            total_duration = float(probe_out)
        except Exception:
            total_duration = sum(t["duration"] for t in tts_results)

        fade_len = min(2.5, total_duration / 3.0)
        fade_start = max(0.0, total_duration - fade_len)

        # Áp dụng filter afade out cho BGM
        filter_complex = (
            f"[0:a]volume=1.0[voice];"
            f"[1:a]volume={vol},afade=t=out:st={fade_start:.2f}:d={fade_len:.2f}[bgm];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        cmd_mix = [
            "ffmpeg", "-y",
            "-i", raw_concat_video,
            "-stream_loop", "-1", "-i", bgm_path,
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            final_output_path
        ]
        subprocess.run(cmd_mix, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return final_output_path
