"""
Script Generator - Phân tích bài báo thành danh sách scenes theo chuẩn biên tập báo chí thời sự.
Bố cục chuẩn hóa theo layout mẫu:
- Frame 1 (title_hero): Tiêu đề bài viết + hình nền đầy đủ (như Hình 1).
- Các Frame chi tiết (news_detail): Nền tối mờ + ảnh inset bo tròn + badge đỏ diễn biến + nội dung lớn (như Hình 2).
- Frame kết (follow): Theo dõi để xem thêm nhiều tin hot (như Hình 3).
"""
import re
import os
import json
from typing import Optional, List, Dict


def _clean_text(text: str) -> str:
    """Xóa khoảng trắng thừa và ký tự rác."""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _split_into_paragraphs(content: str, title: str) -> List[str]:
    """Tách bài báo thành các đoạn văn hoàn chỉnh có nghĩa."""
    raw_paras = [p.strip() for p in content.split('\n') if len(p.strip()) > 30]
    cleaned = []
    title_lower = title.strip().lower()

    for p in raw_paras:
        p_clean = _clean_text(p)
        if p_clean.lower() == title_lower:
            continue
        if len(p_clean) < 40 and any(k in p_clean.lower() for k in ['ảnh:', 'nguồn:', 'theo ', 'bài, ảnh:']):
            continue
        cleaned.append(p_clean)

    return cleaned


def _extract_coherent_sentences(paragraph: str, max_words: int = 40) -> str:
    """
    Trích xuất các câu trọn vẹn trong đoạn văn để đọc không bị cụt.
    Đảm bảo kết thúc bằng dấu chấm hoàn chỉnh.
    """
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', paragraph) if len(s.strip()) > 15]
    if not sents:
        return paragraph

    result_sents = []
    total_words = 0
    for s in sents:
        words_count = len(s.split())
        result_sents.append(s)
        total_words += words_count
        if total_words >= max_words:
            break

    res = " ".join(result_sents)
    if not res.endswith(('.', '!', '?')):
        res += '.'
    return res


def parse_article_to_scenes(
    article: dict,
    duration_seconds: int = 60,
    api_key: Optional[str] = None,
) -> dict:
    """
    Phân tích bài báo thành list scenes:
    - Frame 1: Title Hero (tương tự hình 1)
    - Frame 2, 3, 4: News Detail với badge đỏ & ảnh inset (tương tự hình 2)
    - Frame Cuối: Follow Outro (tương tự hình 3)
    """
    title   = article.get("title", "Tin tức mới nhất")
    content = article.get("content", "")
    source  = article.get("source", "Tin tức")

    # Nếu có API key Gemini
    if api_key:
        scenes = _gemini_generate_scenes(title, content, source, duration_seconds, api_key)
        if scenes:
            return {"title": title, "source": source, "images": article.get("images", []), "scenes": scenes}

    paragraphs = _split_into_paragraphs(content, title)
    if not paragraphs:
        paragraphs = [title]

    scenes = []

    # 1. FRAME 1: Title Hero (Tiêu đề bài viết kèm hình - Hình 1)
    lead_text = _extract_coherent_sentences(paragraphs[0], max_words=30)
    scenes.append({
        "id": 1,
        "type": "title_hero",
        "headline": title[:65],
        "text": lead_text,
        "motion": "zoom_in",
    })

    # Tìm các đoạn văn tương ứng theo chủ đề
    event_para = None
    for p in paragraphs[1:]:
        p_l = p.lower()
        if any(k in p_l for k in ["lái xe", "vượt một", "lấn sang", "va chạm", "tông vào", "chèn qua", "đánh lái", "lưu thông", "theo bản án", "ngày"]):
            event_para = p
            break
    if not event_para and len(paragraphs) > 1:
        event_para = paragraphs[1]

    # Đoạn phán quyết
    verdict_para = None
    for p in paragraphs[1:]:
        p_l = p.lower()
        if p != event_para and any(k in p_l for k in ["tuyên phạt", "hđxx buộc", "bồi thường", "án tù", "tháng tù", "năm tù", "phán quyết", "tử vong", "bị cáo"]):
            verdict_para = p
            break

    # Đoạn tình tiết bổ sung
    detail_para = None
    for p in paragraphs[1:]:
        p_l = p.lower()
        if p != event_para and p != verdict_para and any(k in p_l for k in ["xác định", "có lỗi", "kết luận", "hậu quả", "quy định", "giảm nhẹ", "khắc phục", "gia đình"]):
            detail_para = p
            break

    # 2. FRAME 2: Diễn biến vụ việc (Hình 2)
    if event_para:
        event_text = _extract_coherent_sentences(event_para, max_words=40)
        scenes.append({
            "id": 2,
            "type": "news_detail",
            "headline": "DIỄN BIẾN VỤ VIỆC",
            "text": event_text,
            "motion": "pan",
        })

    # 3. FRAME 3: Phán quyết / Kết quả xử lý (Hình 2 layout)
    if verdict_para:
        verdict_text = _extract_coherent_sentences(verdict_para, max_words=40)
        scenes.append({
            "id": 3,
            "type": "news_detail",
            "headline": "PHÁN QUYẾT CỦA TÒA ÁN",
            "text": verdict_text,
            "motion": "zoom_out",
        })

    # 4. FRAME 4: Tình tiết / Trách nhiệm (Hình 2 layout)
    if detail_para:
        detail_text = _extract_coherent_sentences(detail_para, max_words=38)
        scenes.append({
            "id": 4,
            "type": "news_detail",
            "headline": "TÌNH TIẾT XỬ LÝ",
            "text": detail_text,
            "motion": "zoom_in",
        })

    # Nếu bài ngắn hơn, bổ sung thêm đoạn chi tiết khác để video đủ độ dài
    if len(scenes) < 3:
        used_texts = {sc["text"] for sc in scenes}
        for p in paragraphs[1:]:
            p_text = _extract_coherent_sentences(p, max_words=35)
            if p_text not in used_texts:
                scenes.append({
                    "id": len(scenes) + 1,
                    "type": "news_detail",
                    "headline": "THÔNG TIN CHI TIẾT",
                    "text": p_text,
                    "motion": "pan",
                })
                used_texts.add(p_text)
                if len(scenes) >= 3:
                    break

    # 5. FRAME CUỐI: Theo dõi để xem thêm (Hình 3)
    scenes.append({
        "id": len(scenes) + 1,
        "type": "follow",
        "headline": "THEO DÕI ĐỂ XEM THÊM",
        "text": "Bấm theo dõi kênh để cập nhật liên tục các tin tức nóng nhất.",
        "motion": "static",
    })

    # Đánh lại ID cho chuẩn thứ tự 1, 2, 3...
    for i, sc in enumerate(scenes, 1):
        sc["id"] = i

    return {
        "title": title,
        "source": source,
        "images": article.get("images", []),
        "scenes": scenes,
    }


def _gemini_generate_scenes(title, content, source, duration, api_key) -> list:
    """Dùng Gemini API sinh scenes theo đúng cấu trúc yêu cầu."""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = f"""Bạn là biên tập viên video tin tức TikTok chuyên nghiệp.
Hãy phân tích bài báo sau và tạo danh sách 4-5 scenes cho video thời sự dọc 9:16 ({duration} giây) theo đúng cấu trúc:
1. Scene 1: type="title_hero", Tiêu đề to giật gân + lời dẫn mở đầu (Lead).
2. Các Scene tiếp theo (2, 3...): type="news_detail", diễn biến, tình tiết, phán quyết với headline ngắn gọn (ví dụ: DIỄN BIẾN VỤ VIỆC, PHÁN QUYẾT CỦA TÒA...).
3. Scene cuối cùng: type="follow", headline="THEO DÕI ĐỂ XEM THÊM", text="Bấm theo dõi kênh để cập nhật tin tức nóng hổi mỗi ngày."

BÀI BÁO:
Tiêu đề: {title}
Nguồn: {source}
Nội dung: {content[:3500]}

YÊU CẦU QUAN TRỌNG:
1. Mỗi scene phải là một đoạn văn / ý trọn vẹn, kết thúc bằng dấu chấm rõ ràng, TUYỆT ĐỐI KHÔNG cắt câu cụt ngủn hoặc ngắt giữa chừng.

Trả về duy nhất định dạng JSON sau (KHÔNG bọc trong markdown ```json):
[
  {{
    "id": 1,
    "type": "title_hero",
    "headline": "Tiêu đề ngắn gọn giật gân (<60 ký tự)",
    "text": "Lời đọc mở đầu đầy đủ ý nghĩa.",
    "motion": "zoom_in"
  }},
  {{
    "id": 2,
    "type": "news_detail",
    "headline": "DIỄN BIẾN VỤ VIỆC",
    "text": "Diễn biến chi tiết trọn vẹn câu từ bài báo.",
    "motion": "pan"
  }},
  {{
    "id": 3,
    "type": "news_detail",
    "headline": "PHÁN QUYẾT CỦA TÒA ÁN",
    "text": "Thông tin xử lý nghiêm minh trọn vẹn câu.",
    "motion": "zoom_out"
  }},
  {{
    "id": 4,
    "type": "follow",
    "headline": "THEO DÕI ĐỂ XEM THÊM",
    "text": "Bấm theo dõi kênh để cập nhật nhiều tin hot.",
    "motion": "static"
  }}
]
"""
        resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        raw = resp.text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'```$', '', raw).strip()
        scenes = json.loads(raw)
        return scenes
    except Exception as e:
        print(f"Gemini error: {e}")
        return []
