"""
Main FastAPI server
"""
import os
import uuid
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


class RenderRequest(BaseModel):
    source: str
    images: List[str] = []
    scenes: List[dict]
    voice: str = "vi-VN-HoaiMyNeural"
    zalo_key: Optional[str] = "c6B974D16LbRHcSR1hRGGswtXV0LUOr6"
    use_bgm: bool = True
    bgm_volume: float = 0.15


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


@app.get("/api/bgm-status")
def bgm_status():
    """Kiểm tra xem đã có nhạc nền mặc định chưa."""
    has_bgm = os.path.exists(DEFAULT_BGM_PATH) and os.path.getsize(DEFAULT_BGM_PATH) > 0
    size_kb = round(os.path.getsize(DEFAULT_BGM_PATH) / 1024, 1) if has_bgm else 0
    return {
        "has_bgm": has_bgm,
        "size_kb": size_kb,
        "default_volume": 0.15
    }


@app.post("/api/parse-article")
async def parse_article(req: ParseRequest):
    try:
        article = extract_article_content(req.url_or_text)
        if not article["content"] or len(article["content"]) < 20:
            raise Exception("Không đọc được nội dung bài báo.")
        parsed = parse_article_to_scenes(
            article,
            duration_seconds=req.duration,
            api_key=req.gemini_key or None,
        )
        return {"success": True, "data": parsed}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/render-video")
async def render_video(req: RenderRequest):
    job_id  = str(uuid.uuid4())[:8]
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    try:
        # 1. Generate TTS cho từng scene (hỗ trợ cả Zalo AI lẫn Edge-TTS)
        tts_results = []
        for idx, scene in enumerate(req.scenes):
            audio_path = os.path.join(job_dir, f"audio_{idx:02d}.mp3")
            result = generate_tts(
                text=scene["text"],
                voice=req.voice,
                audio_path=audio_path,
                zalo_api_key=req.zalo_key or "c6B974D16LbRHcSR1hRGGswtXV0LUOr6"
            )
            tts_results.append(result)

        # 2. Render video (kèm nhạc nền BGM nếu bật)
        final_name = f"news_{job_id}.mp4"
        final_path = os.path.join(job_dir, final_name)

        bgm_to_use = DEFAULT_BGM_PATH if (req.use_bgm and os.path.exists(DEFAULT_BGM_PATH)) else None

        render_full_video(
            scenes=req.scenes,
            source_name=req.source,
            article_images=req.images,
            tts_results=tts_results,
            work_dir=job_dir,
            final_output_path=final_path,
            bgm_path=bgm_to_use,
            bgm_volume=req.bgm_volume,
        )

        return {"success": True, "video_url": f"/outputs/{job_id}/{final_name}"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    idx = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(idx)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
