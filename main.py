"""
Main FastAPI server
"""
import os
import re
import time
import uuid
import unicodedata
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from scraper import extract_article_content, extract_multiple_articles
from script_generator import parse_article_to_scenes
from tts import generate_tts
from video_pipeline import render_full_video

app = FastAPI(title="AI News Video Maker Pro")

import shutil
from fastapi import UploadFile, File

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

DEFAULT_BGM_PATH = os.path.join(ASSETS_DIR, "default_bgm.mp3")

app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


class ParseRequest(BaseModel):
    url_or_text: str = ""
    urls: List[str] = []  # Danh sách nhiều URL cho chế độ tổng hợp
    duration: int = 60
    gemini_key: Optional[str] = None
    video_style: str = "tin_tuc"  # tin_tuc | vu_an | khoa_hoc | tong_hop


import unicodedata

def slugify_title(text: str) -> str:
    """Chuyển tiêu đề tiếng Việt có dấu thành chuỗi không dấu dạng slug: vd cong-an-phu-tho-..."""
    if not text:
        return "news"
    text = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    text = text.replace('đ', 'd').replace('Đ', 'D')
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower()
    text = re.sub(r'[\s_-]+', '-', text)
    slug = text[:120].strip('-')
    return slug or "news"


class RenderRequest(BaseModel):
    title: Optional[str] = ""
    source: str
    images: List[str] = []
    scenes: List[dict]
    voice: str = "zalo-3"
    voice_speed: float = 1.05
    zalo_key: Optional[str] = "c6B974D16LbRHcSR1hRGGswtXV0LUOr6"
    use_bgm: bool = True
    bgm_volume: float = 0.10


@app.post("/api/upload-bgm")
async def upload_bgm(file: UploadFile = File(...)):
    """Upload và lưu file nhạc nền MP3 mặc định dùng mãi mãi cho tất cả video."""
    try:
        content = await file.read()
        if len(content) < 1000:
            raise Exception("File âm thanh không hợp lệ hoặc quá nhỏ.")
        with open(DEFAULT_BGM_PATH, "wb") as f:
            f.write(content)
        return {
            "success": True,
            "filename": file.filename,
            "size_kb": round(len(content) / 1024, 1),
            "message": "Đã lưu nhạc nền mặc định thành công!"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Upload ảnh riêng cho từng frame phân cảnh."""
    try:
        img_id = str(uuid.uuid4())[:8]
        ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
        save_name = f"user_img_{img_id}{ext}"
        save_path = os.path.join(OUTPUT_DIR, save_name)
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
        return {
            "success": True,
            "url": f"/outputs/{save_name}",
            "filename": file.filename
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/bgm-status")
def bgm_status():
    """Kiểm tra xem đã có nhạc nền mặc định chưa."""
    has_bgm = os.path.exists(DEFAULT_BGM_PATH) and os.path.getsize(DEFAULT_BGM_PATH) > 0
    size_kb = round(os.path.getsize(DEFAULT_BGM_PATH) / 1024, 1) if has_bgm else 0
    return {
        "has_bgm": has_bgm,
        "size_kb": size_kb,
        "default_volume": 0.10
    }


class VoicePreviewRequest(BaseModel):
    voice: str
    voice_speed: float = 1.05
    zalo_key: Optional[str] = None


@app.post("/api/preview-voice")
def preview_voice(req: VoicePreviewRequest):
    """Sinh một đoạn audio mẫu ngắn (3-4 giây) để người dùng nghe thử giọng đọc và tốc độ."""
    try:
        sample_text = "Xin chào, đây là giọng đọc thử nghiệm của Tin Nhanh 360 với tốc độ được chọn."
        safe_voice = re.sub(r'[^a-zA-Z0-9_-]', '', req.voice)
        preview_filename = f"preview_{safe_voice}_{int(req.voice_speed*100)}.mp3"
        preview_path = os.path.join(OUTPUT_DIR, preview_filename)

        res = generate_tts(
            text=sample_text,
            voice=req.voice,
            audio_path=preview_path,
            zalo_api_key=req.zalo_key or "c6B974D16LbRHcSR1hRGGswtXV0LUOr6",
            voice_speed=req.voice_speed
        )
        if not res or res.get("is_silent"):
            raise Exception("Không thể tạo file âm thanh nghe thử.")

        return {
            "success": True,
            "audio_url": f"/outputs/{preview_filename}?t={int(time.time())}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


from youtube_uploader import is_youtube_configured, is_youtube_authenticated, upload_to_youtube

class YouTubeUploadRequest(BaseModel):
    video_url: str
    title: str
    description: Optional[str] = ""
    privacy: str = "public"  # 'public', 'unlisted', or 'private'


@app.get("/api/youtube-status")
def youtube_status():
    """Kiểm tra trạng thái cấu hình YouTube OAuth và token."""
    return {
        "configured": is_youtube_configured(),
        "authenticated": is_youtube_authenticated(),
    }


yt_upload_jobs = {}

def execute_youtube_upload(upload_id: str, video_abs_path: str, title: str, description: str, privacy: str):
    def on_progress(percent: int, message: str):
        if upload_id in yt_upload_jobs:
            yt_upload_jobs[upload_id].update({
                "percent": percent,
                "message": message,
            })

    try:
        yt_upload_jobs[upload_id].update({
            "status": "uploading",
            "percent": 5,
            "message": "Đang kết nối YouTube..."
        })
        result = upload_to_youtube(
            video_path=video_abs_path,
            title=title,
            description=description,
            privacy_status=privacy,
            progress_callback=on_progress
        )
        yt_upload_jobs[upload_id].update({
            "status": "completed",
            "percent": 100,
            "message": "Đăng video thành công!",
            "result": result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        err_msg = str(e)
        if "client_secrets.json" in err_msg:
            err_msg = "Không tìm thấy file client_secrets.json trên server."
        elif "consent" in err_msg or "authorization" in err_msg.lower():
            err_msg = "Chưa cấp quyền Google OAuth hoặc link cấp quyền đã hết hạn. Vui lòng thử lại."
        yt_upload_jobs[upload_id].update({
            "status": "failed",
            "message": f"Thất bại: {err_msg}",
            "error": err_msg
        })


@app.post("/api/upload-youtube")
def upload_youtube_endpoint(req: YouTubeUploadRequest):
    """Bắt đầu tiến trình upload YouTube Shorts với tracking tiến độ."""
    try:
        clean_url = req.video_url.lstrip("/")
        if clean_url.startswith("outputs/"):
            rel_path = clean_url[len("outputs/"):]
        else:
            rel_path = clean_url
        video_abs_path = os.path.join(OUTPUT_DIR, rel_path)

        if not os.path.exists(video_abs_path):
            raise Exception(f"Không tìm thấy file video trên server: {video_abs_path}")

        import threading
        upload_id = str(uuid.uuid4())[:8]
        yt_upload_jobs[upload_id] = {
            "status": "starting",
            "percent": 2,
            "message": "Đang chuẩn bị video...",
            "result": None,
            "error": None
        }

        t = threading.Thread(
            target=execute_youtube_upload,
            args=(upload_id, video_abs_path, req.title, req.description, req.privacy),
            daemon=True
        )
        t.start()

        return {"success": True, "upload_id": upload_id}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/youtube-upload-status/{upload_id}")
def youtube_upload_status(upload_id: str):
    """Kiểm tra tiến trình upload YouTube theo phần trăm."""
    if upload_id in yt_upload_jobs:
        return yt_upload_jobs[upload_id]
    raise HTTPException(status_code=404, detail="Upload job not found")


@app.post("/api/parse-article")
async def parse_article(req: ParseRequest):
    try:
        video_style = req.video_style or "tin_tuc"

        # Chế độ tổng hợp nhiều bài (2-3 URL)
        if video_style == "tong_hop" and req.urls and len(req.urls) > 0:
            valid_urls = [u.strip() for u in req.urls if u.strip().startswith("http")]
            if len(valid_urls) == 0:
                raise Exception("Vui lòng nhập ít nhất 1 link bài báo hợp lệ (bắt đầu bằng http).")
            if len(valid_urls) == 1:
                article = extract_article_content(valid_urls[0])
            else:
                article = extract_multiple_articles(valid_urls)
        else:
            # Chế độ 1 bài đơn (tin tức, vụ án, khoa học)
            input_text = req.url_or_text.strip()
            if not input_text:
                raise Exception("Vui lòng nhập link bài báo hoặc nội dung văn bản.")
            article = extract_article_content(input_text)

        if not article["content"] or len(article["content"].strip()) < 20 or article["content"].startswith("Không thể đọc nội dung"):
            raise Exception(f"Không cào được chữ từ link (nội dung rỗng hoặc bị trang báo chặn/yêu cầu captcha). Hãy thử dán trực tiếp đoạn văn bản bài báo vào ô.")

        parsed = parse_article_to_scenes(
            article,
            duration_seconds=req.duration,
            api_key=req.gemini_key or None,
            video_style=video_style,
        )
        return {"success": True, "data": parsed}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# Storage for render jobs (in-memory + disk persistent)
jobs_status = {}
import json

def update_job_progress(job_id: str, step: str, message: str, percent: int):
    if job_id not in jobs_status:
        jobs_status[job_id] = {}
    jobs_status[job_id].update({
        "step": step,
        "message": message,
        "percent": percent,
    })
    try:
        jdir = os.path.join(OUTPUT_DIR, job_id)
        os.makedirs(jdir, exist_ok=True)
        with open(os.path.join(jdir, "status.json"), "w", encoding="utf-8") as f:
            json.dump(jobs_status[job_id], f, ensure_ascii=False)
    except Exception:
        pass


def execute_render_job(job_id: str, req_data: dict):
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    try:
        scenes = req_data["scenes"]
        total_scenes = len(scenes)

        # 1. TTS Generation
        update_job_progress(job_id, "tts", f"Đang tạo giọng đọc AI (0/{total_scenes})...", 5)
        tts_results = []
        for idx, scene in enumerate(scenes):
            update_job_progress(
                job_id,
                "tts",
                f"Đang sinh giọng đọc cảnh {idx + 1}/{total_scenes}: {scene.get('headline', '')[:30]}",
                5 + int(30 * (idx / max(1, total_scenes)))
            )
            audio_path = os.path.join(job_dir, f"audio_{idx:02d}.mp3")
            result = generate_tts(
                text=scene["text"],
                voice=req_data["voice"],
                audio_path=audio_path,
                zalo_api_key=req_data.get("zalo_key") or "c6B974D16LbRHcSR1hRGGswtXV0LUOr6",
                voice_speed=float(req_data.get("voice_speed", 1.05))
            )
            if not result or result.get("duration", 0) <= 0.2:
                raise Exception(f"Không thể tạo giọng đọc cho cảnh {idx + 1} ('{scene.get('headline', '')}'). Vui lòng kiểm tra lại kết nối mạng hoặc đổi giọng đọc khác.")
            if result.get("is_silent"):
                raise Exception(f"Không kết nối được dịch vụ giọng đọc AI cho cảnh {idx + 1}. Vui lòng kiểm tra lại kết nối Internet hoặc tài khoản giọng đọc.")
            tts_results.append(result)

        # 2. Render Scene Clips & Pipeline
        update_job_progress(job_id, "render", "Đang xử lý layout đồ họa và hiệu ứng chuyển động cảnh...", 38)

        def on_video_progress(step_key, step_msg, factor):
            # factor từ 0.0 -> 1.0 (chiếm từ 40% đến 95%)
            cur_pct = 40 + int(factor * 55)
            update_job_progress(job_id, step_key, step_msg, cur_pct)

        # Đặt tên file bằng tiêu đề bài báo không dấu, ví dụ: cong-an-phu-tho-khoi-to-...mp4
        article_title = req_data.get("title") or ""
        if not article_title and scenes:
            # Lấy tiêu đề từ scene đầu tiên nếu không có title
            article_title = scenes[0].get("headline") or ""

        title_slug = slugify_title(article_title)
        final_name = f"{title_slug}.mp4"
        final_path = os.path.join(job_dir, final_name)
        use_bgm = req_data.get("use_bgm", True)
        bgm_to_use = DEFAULT_BGM_PATH if (use_bgm and os.path.exists(DEFAULT_BGM_PATH)) else None

        render_full_video(
            scenes=scenes,
            source_name=req_data["source"],
            article_images=req_data.get("images", []),
            tts_results=tts_results,
            work_dir=job_dir,
            final_output_path=final_path,
            bgm_path=bgm_to_use,
            bgm_volume=req_data.get("bgm_volume", 0.10),
            progress_callback=on_video_progress,
        )

        update_job_progress(job_id, "complete", "Đã hoàn thành xuất video 9:16 chất lượng cao!", 100)
        jobs_status[job_id]["status"] = "completed"
        jobs_status[job_id]["video_url"] = f"/outputs/{job_id}/{final_name}"
        jobs_status[job_id]["filename"] = final_name

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs_status[job_id]["status"] = "failed"
        jobs_status[job_id]["error"] = str(e)
        jobs_status[job_id]["message"] = f"Lỗi: {e}"


@app.post("/api/render-video")
async def render_video(req: RenderRequest):
    import threading
    job_id = str(uuid.uuid4())[:8]
    jobs_status[job_id] = {
        "status": "processing",
        "step": "init",
        "message": "Khởi động tiến trình render...",
        "percent": 2,
        "video_url": None,
        "error": None,
    }

    req_data = {
        "title": req.title,
        "source": req.source,
        "images": req.images,
        "scenes": req.scenes,
        "voice": req.voice,
        "voice_speed": req.voice_speed,
        "zalo_key": req.zalo_key,
        "use_bgm": req.use_bgm,
        "bgm_volume": req.bgm_volume,
    }

    t = threading.Thread(target=execute_render_job, args=(job_id, req_data), daemon=True)
    t.start()

    return {"success": True, "job_id": job_id}


@app.get("/api/render-status/{job_id}")
def get_render_status(job_id: str):
    if job_id in jobs_status:
        return jobs_status[job_id]
    
    # Fallback kiểm tra file status.json từ ổ đĩa
    status_file = os.path.join(OUTPUT_DIR, job_id, "status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                jobs_status[job_id] = data
                return data
        except Exception:
            pass
            
    raise HTTPException(status_code=404, detail="Job not found")


@app.get("/")
def root():
    idx = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(idx)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
