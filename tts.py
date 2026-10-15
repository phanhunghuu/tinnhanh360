"""
TTS Module - Hỗ trợ cả Zalo AI TTS (chất lượng cao) và Edge-TTS (miễn phí không giới hạn).
"""
import asyncio
import edge_tts
import subprocess
import os
import requests
import concurrent.futures
from typing import Optional


ZALO_VOICES = {
    "zalo-1": {"speaker_id": 1, "name": "Zalo AI - Nữ Miền Nam"},
    "zalo-2": {"speaker_id": 2, "name": "Zalo AI - Nữ Miền Bắc (Chuẩn VTV)"},
    "zalo-3": {"speaker_id": 3, "name": "Zalo AI - Nam Miền Nam"},
    "zalo-4": {"speaker_id": 4, "name": "Zalo AI - Nam Miền Bắc (Trầm ấm)"},
    "zalo-5": {"speaker_id": 5, "name": "Zalo AI - Nữ Miền Bắc 2"},
    "zalo-6": {"speaker_id": 6, "name": "Zalo AI - Nữ Miền Nam 2"},
}


def _generate_zalo_tts(text: str, voice: str, audio_path: str, api_key: str, speed: float = 1.1) -> bool:
    """Gọi API Zalo AI để sinh file âm thanh wav/mp3 với polling chờ file ready."""
    import time
    speaker_id = ZALO_VOICES.get(voice, {}).get("speaker_id", 2)
    clean_text = (text or "").strip()
    if not clean_text:
        clean_text = "..."

    headers = {"apikey": api_key}
    data = {
        "input": clean_text,
        "speaker_id": speaker_id,
        "speed": speed,
    }

    try:
        resp = requests.post("https://api.zalo.ai/v1/tts/synthesize", headers=headers, data=data, timeout=15)
        res_json = resp.json()
        if res_json.get("error_code") == 0 and "data" in res_json and "url" in res_json["data"]:
            audio_url = res_json["data"]["url"]

            # Zalo AI sinh file bất đồng bộ trên CDN, cần poll 0.5s - 1s để file sẵn sàng
            audio_content = None
            for _ in range(12):
                time.sleep(0.5)
                audio_resp = requests.get(audio_url, timeout=10)
                if audio_resp.status_code == 200 and len(audio_resp.content) > 500:
                    audio_content = audio_resp.content
                    break

            if audio_content:
                temp_wav = audio_path + ".tmp.wav"
                with open(temp_wav, "wb") as f:
                    f.write(audio_content)

                subprocess.run([
                    "ffmpeg", "-y", "-i", temp_wav,
                    "-ar", "44100", "-ac", "2", "-b:a", "128k",
                    audio_path
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
                return True
            else:
                print(f"Zalo audio polling timed out for url: {audio_url}")
        else:
            print(f"Zalo AI error: {res_json}")
    except Exception as e:
        print(f"Zalo TTS exception: {e}")

    return False


async def _stream_edge_tts(text: str, voice: str, audio_path: str, rate: str = "+30%") -> list:
    """Stream edge-tts có retry tối đa 3 lần."""
    clean_text = text.strip()
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

    print(f"Warning: Edge-TTS failed for text '{text[:40]}...': {last_err}. Using fallback.")
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


def generate_tts(
    text: str,
    voice: str,
    audio_path: str,
    rate: str = "+30%",
    zalo_api_key: Optional[str] = None
) -> dict:
    """
    Sinh audio từ text:
    - Nếu voice là giọng Zalo và có API key -> Gọi Zalo AI TTS (tốc độ đọc nhanh 1.1).
    - Ngược lại -> Gọi Edge-TTS tốc độ +30%.
    """
    text = (text or "").strip()
    if not text:
        text = "..."

    boundaries = []
    use_zalo = voice.startswith("zalo-") and bool(zalo_api_key)

    # Ánh xạ giới tính khi cần fallback sang Edge-TTS
    is_male = voice in ["zalo-3", "zalo-4", "vi-VN-NamMinhNeural"]
    edge_fallback_voice = "vi-VN-NamMinhNeural" if is_male else "vi-VN-HoaiMyNeural"

    if use_zalo:
        success = _generate_zalo_tts(text, voice, audio_path, zalo_api_key, speed=1.1)
        if not success:
            print(f"Zalo AI failed, fallbacking to Edge-TTS ({edge_fallback_voice})...")
            boundaries = _run_in_thread(_stream_edge_tts(text, edge_fallback_voice, audio_path, rate=rate))
    else:
        # Nếu chọn Edge-TTS
        edge_voice = voice if not voice.startswith("zalo-") else edge_fallback_voice
        boundaries = _run_in_thread(_stream_edge_tts(text, edge_voice, audio_path, rate=rate))

    # Chuẩn hóa âm thanh đầu ra về chuẩn 44100Hz Stereo MP3
    try:
        norm_temp = audio_path + ".norm.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "44100", "-ac", "2", "-b:a", "192k",
            norm_temp
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(norm_temp) and os.path.getsize(norm_temp) > 200:
            os.replace(norm_temp, audio_path)
    except Exception as ne:
        print(f"Normalize audio error: {ne}")

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
