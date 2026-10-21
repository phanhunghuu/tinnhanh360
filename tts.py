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

KOKORO_VOICES = {
    "kokoro-hung_thinh": {"voice": "hung_thinh", "name": "Kokoro AI - Hưng Thịnh (Nam - Trầm ấm)", "gender": "male"},
    "kokoro-phat_tai": {"voice": "phat_tai", "name": "Kokoro AI - Phát Tài (Nam - Tự nhiên)", "gender": "male"},
    "kokoro-thanh_dat": {"voice": "thanh_dat", "name": "Kokoro AI - Thành Đạt (Nam - Rõ ràng)", "gender": "male"},
    "kokoro-duc_an": {"voice": "duc_an", "name": "Kokoro AI - Đức An (Nam - Trẻ trung)", "gender": "male"},
    "kokoro-manh_dung": {"voice": "manh_dung", "name": "Kokoro AI - Mạnh Dũng (Nam - Uy quyền)", "gender": "male"},
    "kokoro-tuan_ngoc": {"voice": "tuan_ngoc", "name": "Kokoro AI - Tuấn Ngọc (Nam - Đĩnh đạc)", "gender": "male"},
    "kokoro-diem_trinh": {"voice": "diem_trinh", "name": "Kokoro AI - Diễm Trinh (Nữ - Truyền cảm)", "gender": "female"},
    "kokoro-my_yen": {"voice": "my_yen", "name": "Kokoro AI - Mỹ Yến (Nữ - Ngọt ngào)", "gender": "female"},
    "kokoro-ngoc_huyen": {"voice": "ngoc_huyen", "name": "Kokoro AI - Ngọc Huyền (Nữ - Dịu dàng)", "gender": "female"},
    "kokoro-mai_linh": {"voice": "mai_linh", "name": "Kokoro AI - Mai Linh (Nữ - Nhẹ nhàng)", "gender": "female"},
    "kokoro-thuc_trinh": {"voice": "thuc_trinh", "name": "Kokoro AI - Thục Trinh (Nữ - Thanh thoát)", "gender": "female"},
}

_kokoro_instances = {}

def get_kokoro_tts(voice_name: str):
    """Lấy hoặc khởi tạo instance KokoroVietnamese (cache theo giọng)."""
    global _kokoro_instances
    if voice_name not in _kokoro_instances:
        from kokoro_vietnamese import KokoroVietnamese
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _kokoro_instances[voice_name] = KokoroVietnamese(device=device, voice=voice_name)
    return _kokoro_instances[voice_name]


import re
from num2words import num2words

def normalize_vietnamese_text_for_tts(text: str) -> str:
    """
    Chuẩn hóa các con số, ngày tháng, phần trăm, nhiệt độ thành chữ tiếng Việt
    giúp mô hình Kokoro AI đọc tròn vành rõ chữ 100%.
    """
    if not text:
        return ""

    # 1. Ngày tháng năm: 15/10/2026 hoặc 15-10-2026
    def _replace_date(m):
        prefix = m.group(1) or ''
        d, mth, y = int(m.group(2)), int(m.group(3)), int(m.group(4))
        date_words = f'{num2words(d, lang="vi")} tháng {num2words(mth, lang="vi")} năm {num2words(y, lang="vi")}'
        if 'ngày' in prefix.lower():
            return f'{prefix}{date_words}'
        return f'{prefix}ngày {date_words}'

    text = re.sub(r'(\bngày\s+)?\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', _replace_date, text, flags=re.IGNORECASE)

    # 2. Ngày/tháng không có năm: 15/10
    def _replace_dm(m):
        prefix = m.group(1) or ''
        d, mth = int(m.group(2)), int(m.group(3))
        dm_words = f'{num2words(d, lang="vi")} tháng {num2words(mth, lang="vi")}'
        if 'ngày' in prefix.lower():
            return f'{prefix}{dm_words}'
        return f'{prefix}ngày {dm_words}'

    text = re.sub(r'(\bngày\s+)?\b(\d{1,2})[/](\d{1,2})\b', _replace_dm, text, flags=re.IGNORECASE)

    # 3. Đổi số có dấu chấm/phẩy hàng nghìn trước (ví dụ 990.000 hoặc 1,500,000 -> chín trăm...)
    def _clean_thousands(m):
        raw = m.group(0).replace('.', '').replace(',', '')
        return num2words(int(raw), lang='vi')
    text = re.sub(r'\b\d{1,3}(?:[.,]\d{3})+\b', _clean_thousands, text)

    # 4. Xử lý số thập phân tiếng Việt: 0,5 hoặc 1.5 hoặc 0,05 hoặc 12,75 -> không phẩy năm
    def _replace_decimal(m):
        int_part = int(m.group(1))
        dec_str = m.group(2)
        int_words = num2words(int_part, lang='vi')
        
        # Nếu có số 0 ở đầu phần thập phân (ví dụ 05 -> không năm)
        if dec_str.startswith('0'):
            dec_words = " ".join(num2words(int(d), lang='vi') for d in dec_str)
        else:
            dec_words = num2words(int(dec_str), lang='vi')
        return f'{int_words} phẩy {dec_words}'

    # Bắt số thập phân có 1 hoặc 2 chữ số sau dấu phẩy/chấm (không lẫn với hàng nghìn 3 chữ số)
    text = re.sub(r'\b(\d+)[,.](\d{1,2})\b', _replace_decimal, text)

    # 5. Phần trăm: 25% hoặc 0,8% -> phần trăm
    text = re.sub(r'(\d+)\s*%', lambda m: f'{num2words(int(m.group(1)), lang="vi")} phần trăm', text)
    text = re.sub(r'%', ' phần trăm', text)

    # 6. Nhiệt độ âm / độ C: -46 độ C, 35°C
    text = re.sub(r'-\s*(\d+)\s*(?:độ\s*C|°C)', lambda m: f'âm {num2words(int(m.group(1)), lang="vi")} độ C', text)
    text = re.sub(r'(\d+)\s*°C', lambda m: f'{num2words(int(m.group(1)), lang="vi")} độ C', text)
    text = re.sub(r'(?<=\s)-\s*(\d+)', lambda m: f'âm {num2words(int(m.group(1)), lang="vi")}', text)

    # 7. Số thứ tự: Số 3, Top 5
    text = re.sub(r'\b(Số|Top|Mục)\s*(\d+)\b', lambda m: f'{m.group(1)} {num2words(int(m.group(2)), lang="vi")}', text, flags=re.IGNORECASE)

    # 8. Số nguyên còn lại
    text = re.sub(r'\b\d+\b', lambda m: num2words(int(m.group(0)), lang='vi'), text)

    return text


def _generate_kokoro_tts(text: str, voice: str, audio_path: str, speed: float = 1.05) -> bool:
    """Sinh audio bằng mô hình Kokoro-Vietnamese AI 100% offline, miễn phí."""
    import soundfile as sf
    kokoro_info = KOKORO_VOICES.get(voice)
    voice_key = kokoro_info["voice"] if kokoro_info else "diem_trinh"

    clean_text = (text or "").strip()
    if not clean_text:
        clean_text = "..."

    # Chuẩn hóa số và ngày tháng thành chữ trước khi nạp vào Kokoro
    clean_text = normalize_vietnamese_text_for_tts(clean_text)

    try:
        tts = get_kokoro_tts(voice_key)
        audio, _ = tts.synthesize(clean_text, speed=speed)
        if audio is None or len(audio) == 0:
            return False

        temp_wav = audio_path + ".tmp.wav"
        sf.write(temp_wav, audio, 24000)

        # Chuyển đổi và chuẩn hóa âm thanh sang mp3 44100Hz Stereo
        subprocess.run([
            "ffmpeg", "-y", "-i", temp_wav,
            "-ar", "44100", "-ac", "2", "-b:a", "192k",
            audio_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        return True
    except Exception as e:
        print(f"Kokoro TTS generation error: {e}")
        return False



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


async def _stream_edge_tts(text: str, voice: str, audio_path: str, rate: str = "+14%", pitch: str = "-3Hz") -> list:
    """Stream edge-tts có retry tối đa 3 lần với rate và pitch được tối ưu chuẩn MC thời sự."""
    clean_text = text.strip()
    if not clean_text or not any(c.isalnum() for c in clean_text):
        clean_text = "..."

    last_err = None
    for attempt in range(3):
        try:
            c = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
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

    print(f"Warning: Edge-TTS failed after 3 attempts: {last_err}.")
    raise RuntimeError(f"Edge-TTS failed after 3 attempts: {last_err}") from last_err


def _run_in_thread(coro):
    """Chạy coroutine trong thread mới để tránh xung đột event loop với FastAPI."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


def generate_tts(
    text: str,
    voice: str,
    audio_path: str,
    rate: str = "+14%",
    zalo_api_key: Optional[str] = None,
    voice_speed: float = 1.05
) -> dict:
    """
    Sinh audio từ text:
    - Nếu voice là Kokoro -> Sinh audio với voice_speed (ví dụ 1.0, 1.15, 1.25...)
    - Nếu voice là Zalo và có API key -> Gọi Zalo AI TTS (tốc độ đọc nhanh voice_speed).
    - Ngược lại -> Gọi Edge-TTS AI Neural với tốc độ tương ứng voice_speed.
    """
    text = (text or "").strip()
    if not text:
        text = "..."

    # Chuẩn hóa số, ngày tháng, phần trăm, số thập phân cho TẤT CẢ giọng đọc (Edge-TTS, Kokoro, Zalo)
    clean_text = normalize_vietnamese_text_for_tts(text)

    boundaries = []
    use_zalo = voice.startswith("zalo-") and bool(zalo_api_key)
    use_kokoro = voice.startswith("kokoro-")

    # Ánh xạ giới tính khi cần fallback sang Edge-TTS
    is_male = voice in ["zalo-3", "zalo-4", "vi-VN-NamMinhNeural", "kokoro-hung_thinh", "kokoro-manh_dung", "kokoro-tuan_ngoc"]
    edge_fallback_voice = "vi-VN-NamMinhNeural" if is_male else "vi-VN-HoaiMyNeural"
    # Edge-TTS can close the stream without audio for the speed + lowered-pitch
    # combination; neutral pitch is reliable at the default 1.10x rate.
    pitch_tuned = "+0Hz"

    # Tính toán rate cho Edge-TTS dựa trên voice_speed
    # Ví dụ: 1.0 -> +0%, 1.15 -> +15%, 1.25 -> +25%
    speed_pct = int(round((voice_speed - 1.0) * 100))
    edge_rate = f"{speed_pct:+d}%" if speed_pct != 0 else "+0%"

    if use_kokoro:
        success = _generate_kokoro_tts(clean_text, voice, audio_path, speed=voice_speed)
        if not success:
            print(f"Kokoro TTS failed, fallbacking to Edge-TTS ({edge_fallback_voice})...")
            boundaries = _run_in_thread(_stream_edge_tts(clean_text, edge_fallback_voice, audio_path, rate=edge_rate, pitch=pitch_tuned))
    elif use_zalo:
        success = _generate_zalo_tts(clean_text, voice, audio_path, zalo_api_key, speed=voice_speed)
        if not success:
            print(f"Zalo AI failed, fallbacking to Edge-TTS ({edge_fallback_voice})...")
            boundaries = _run_in_thread(_stream_edge_tts(clean_text, edge_fallback_voice, audio_path, rate=edge_rate, pitch=pitch_tuned))
    else:
        # Nếu chọn Edge-TTS
        edge_voice = voice if not (voice.startswith("zalo-") or voice.startswith("kokoro-")) else edge_fallback_voice
        boundaries = _run_in_thread(_stream_edge_tts(clean_text, edge_voice, audio_path, rate=edge_rate, pitch=pitch_tuned))

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

    is_silent = False
    try:
        if os.path.exists(audio_path) and os.path.getsize(audio_path) < 1000:
            is_silent = True
    except Exception:
        pass

    return {
        "audio_path": audio_path,
        "duration": duration,
        "sentences": boundaries,
        "is_silent": is_silent,
    }
