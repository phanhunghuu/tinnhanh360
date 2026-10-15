"""
TTS Module - Thu thập audio + sentence timestamps từ Edge-TTS
Được cấu hình tốc độ đọc rate="+30%" theo yêu cầu người dùng.
"""
import asyncio
import edge_tts
import subprocess
import os
import concurrent.futures


async def _stream_tts(text: str, voice: str, audio_path: str, rate: str = "+30%") -> list:
    """
    Stream edge-tts, ghi audio ra file và thu thập SentenceBoundary timestamps.
    Tự động retry tối đa 3 lần nếu mạng chập chờn hoặc dịch vụ bận.
    """
    clean_text = text.strip()
    # Loại bỏ các ký tự đặc biệt hoặc text quá ngắn chỉ có dấu câu gây lỗi NoAudioReceived
    if not clean_text or not any(c.isalnum() for c in clean_text):
        clean_text = "..."

    last_err = None
    for attempt in range(3):
        try:
            c = edge_tts.Communicate(clean_text, voice, rate=rate)
            boundaries = []
            audio_bytes = bytearray()

            async for chunk in c.stream():
                if chunk["type"] == "SentenceBoundary":
                    boundaries.append({
                        "text": chunk["text"],
                        "start": chunk["offset"] / 10_000_000,
                        "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                    })
                elif chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])

            if audio_bytes:
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)
                return boundaries
            else:
                raise edge_tts.exceptions.NoAudioReceived("No audio bytes received from edge-tts")
        except Exception as e:
            last_err = e
            await asyncio.sleep(0.8 * (attempt + 1))

    # Nếu sau 3 lần vẫn lỗi (ví dụ text chỉ có ký tự lạ hoặc dịch vụ Microsoft tạm ngắt)
    # Fallback tạo file audio ngắn bằng ffmpeg để pipeline không bị crash gãy cả video
    print(f"Warning: TTS failed for text '{text[:40]}...': {last_err}. Using fallback.")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "2.0", audio_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return []


def _run_in_thread(coro):
    """Chạy coroutine trong thread mới để tránh xung đột event loop với FastAPI."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


def generate_tts(text: str, voice: str, audio_path: str, rate: str = "+30%") -> dict:
    """
    Chạy TTS tốc độ +30% - an toàn dù gọi từ trong FastAPI async context.
    Returns: {"audio_path", "duration", "sentences": [...]}
    """
    # Xử lý text rỗng
    text = (text or "").strip()
    if not text:
        text = "..."

    boundaries = _run_in_thread(_stream_tts(text, voice, audio_path, rate=rate))

    # Đo duration thực tế
    try:
        probe = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ])
        duration = float(probe.strip())
    except Exception:
        duration = 2.0

    return {
        "audio_path": audio_path,
        "duration": duration,
        "sentences": boundaries,
    }

