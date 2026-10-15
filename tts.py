"""
TTS Module - Thu thập audio + sentence timestamps từ Edge-TTS
Được cấu hình tốc độ đọc tăng lên x1.5 (rate="+50%") theo yêu cầu người dùng.
"""
import asyncio
import edge_tts
import subprocess
import os
import concurrent.futures


async def _stream_tts(text: str, voice: str, audio_path: str, rate: str = "+50%") -> list:
    """
    Stream edge-tts, ghi audio ra file và thu thập SentenceBoundary timestamps.
    Returns: list of {"text", "start", "end"} - seconds
    """
    c = edge_tts.Communicate(text, voice, rate=rate)
    boundaries = []

    with open(audio_path, "wb") as f:
        async for chunk in c.stream():
            if chunk["type"] == "SentenceBoundary":
                boundaries.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                })
            elif chunk["type"] == "audio":
                f.write(chunk["data"])

    return boundaries


def _run_in_thread(coro):
    """Chạy coroutine trong thread mới để tránh xung đột event loop với FastAPI."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


def generate_tts(text: str, voice: str, audio_path: str, rate: str = "+50%") -> dict:
    """
    Chạy TTS tốc độ x1.5 (+50%) - an toàn dù gọi từ trong FastAPI async context.
    Returns: {"audio_path", "duration", "sentences": [...]}
    """
    boundaries = _run_in_thread(_stream_tts(text, voice, audio_path, rate=rate))

    # Đo duration thực tế
    probe = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ])
    duration = float(probe.strip())

    return {
        "audio_path": audio_path,
        "duration": duration,
        "sentences": boundaries,
    }
