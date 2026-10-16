"""
Main FastAPI server
"""
import os
import re
import uuid
import unicodedata
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from scraper import extract_article_content
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
    url_or_text: str
    duration: int = 60
    gemini_key: Optional[str] = None


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


@app.post("/api/parse-article")
async def parse_article(req: ParseRequest):
    try:
        article = extract_article_content(req.url_or_text)
        if not article["content"] or len(article["content"].strip()) < 20 or article["content"].startswith("Không thể đọc nội dung"):
            raise Exception(f"Không cào được chữ từ link (nội dung rỗng hoặc bị trang báo chặn/yêu cầu captcha). Hãy thử dán trực tiếp đoạn văn bản bài báo vào ô.")
        parsed = parse_article_to_scenes(
            article,
            duration_seconds=req.duration,
            api_key=req.gemini_key or None,
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
                zalo_api_key=req_data.get("zalo_key") or "c6B974D16LbRHcSR1hRGGswtXV0LUOr6"
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
