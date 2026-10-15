"""
Script Generator - Phân tích bài báo thành danh sách scenes theo chuẩn biên tập báo chí thời sự.
Bố cục chuẩn hóa theo layout mẫu:
- Frame 1 (title_hero): Tiêu đề bài viết GIỮ NGUYÊN ĐẦY ĐỦ 100% (không cắt bớt), kèm hình nền.
- Các Frame chi tiết (news_detail): Tách theo từng câu trọn vẹn, hiển thị đồng bộ với giọng nói voice.
- Frame kết (follow): Theo dõi để xem thêm nhiều tin hot.
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
    raw_paras = [p.strip() for p in content.split('\n') if len(p.strip()) > 25]
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


def _split_into_sentences(text: str) -> List[str]:
    """Tách văn bản thành danh sách từng câu hoàn chỉnh có nghĩa."""
    raw_sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 15]
    res = []
    for s in raw_sents:
        if not s.endswith(('.', '!', '?')):
            s += '.'
        res.append(s)
    return res


def parse_article_to_scenes(
    article: dict,
    duration_seconds: int = 60,
    api_key: Optional[str] = None,
) -> dict:
    """
    Phân tích bài báo thành list scenes:
    - Frame 1: Title Hero (Tiêu đề bài viết đầy đủ 100%, không cắt bớt)
    - Frame 2, 3, 4: News Detail từng câu trọn vẹn, khớp giọng đọc voice
    - Frame Cuối: Follow Outro
    """
    title   = _clean_text(article.get("title", "Tin tức mới nhất"))
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

    # 1. FRAME 1: Title Hero (Tiêu đề bài viết GIỮ NGUYÊN ĐẦY ĐỦ 100%)
    # Lời đọc chỉ đọc đúng tiêu đề bài báo
    scenes.append({
        "id": 1,
        "type": "title_hero",
        "headline": title,  # Giữ trọn vẹn 100% tiêu đề gốc!
        "text": title,      # Chỉ đọc tiêu đề bài báo, không thừa câu khác
        "motion": "zoom_in",
    })

    # Thu thập tất cả các câu từ bài báo
    all_sentences = []
    for p in paragraphs:
        sents = _split_into_sentences(p)
        all_sentences.extend(sents)

    # ── THUẬT TOÁN TÓM TẮT THÔNG MINH (Smart News Summarizer) ──
    # Lọc bỏ câu rác, câu phụ bàn nhậu, câu dẫn linh tinh
    # Ưu tiên các câu chứa thông tin cốt lõi: Ai, Làm gì, Hậu quả gì, Bị bắt/Phạt thế nào
    KEYWORDS_CORE = [
        "khởi tố", "bắt tạm giam", "tuyên phạt", "án tù", "tử vong", "bị cáo",
        "hđxx", "hành vi", "cơ quan điều tra", "xác định", "kết luận",
        "thiệt hại", "hàng giả", "buôn bán", "sản xuất", "tang vật",
        "vụ án", "nạn nhân", "nguyên nhân", "bồi thường"
    ]
    KEYWORDS_DISCARD = [
        "bàn nhậu", "uống rượu", "lời qua tiếng lại", "quê ở", "sinh năm",
        "sau khi uống", "tiếp tục nhậu", "ngồi uống", "ảnh:", "nguồn:"
    ]

    scored_sents = []
    for idx, sent in enumerate(all_sentences):
        s_lower = sent.lower()
        # Bỏ qua câu quá ngắn hoặc quá dài
        if len(sent) < 35 or len(sent) > 220:
            continue

        score = 0
        # Câu mở đầu đoạn thường chứa ý chính
        if idx in [0, 1]:
            score += 3
        # Điểm cộng cho từ khóa cốt lõi thời sự
        for kw in KEYWORDS_CORE:
            if kw in s_lower:
                score += 2
        # Điểm trừ cho chi tiết vụn vặt
        for kw in KEYWORDS_DISCARD:
            if kw in s_lower:
                score -= 3

        scored_sents.append((score, idx, sent))

    # Lọc bỏ hẳn các câu bị điểm âm hoặc câu chứa chi tiết vụn vặt
    valid_sents = [item for item in scored_sents if item[0] >= 0]
    if not valid_sents:
        valid_sents = scored_sents

    # Sắp xếp lấy 3 câu có điểm chất lượng cao nhất
    valid_sents.sort(key=lambda x: x[0], reverse=True)
    top_candidates = valid_sents[:3]
    # Sắp xếp lại theo trình tự thời gian ban đầu của bài báo
    top_candidates.sort(key=lambda x: x[1])

    selected_sents = [item[2] for item in top_candidates]
    if not selected_sents:
        selected_sents = all_sentences[:2]

    headlines_cycle = [
        "DIỄN BIẾN VỤ VIỆC",
        "KẾT QUẢ ĐIỀU TRA",
        "PHÁN QUYẾT CỦA TÒA ÁN",
        "HẬU QUẢ VỤ VIỆC",
    ]

    for i, sent in enumerate(selected_sents):
        hl = headlines_cycle[i % len(headlines_cycle)]
        s_lower = sent.lower()
        if any(k in s_lower for k in ["tuyên phạt", "tháng tù", "năm tù", "bồi thường", "hđxx", "phán quyết"]):
            hl = "PHÁN QUYẾT CỦA TÒA ÁN"
        elif any(k in s_lower for k in ["khởi tố", "bắt tạm giam", "khám xét", "thu giữ", "tang vật"]):
            hl = "KẾT QUẢ ĐIỀU TRA"
        elif any(k in s_lower for k in ["sáng", "ngày", "chiều", "lái xe", "va chạm", "tông", "lấn sang"]):
            hl = "DIỄN BIẾN VỤ VIỆC"
        elif any(k in s_lower for k in ["hậu quả", "tử vong", "thiệt hại", "hàng giả"]):
            hl = "HẬU QUẢ VỤ VIỆC"

        scenes.append({
            "id": len(scenes) + 1,
            "type": "news_detail",
            "headline": hl,
            "text": sent,
            "motion": "pan" if i % 2 == 0 else "zoom_out",
        })

    # FRAME CUỐI: Theo dõi để xem thêm
    scenes.append({
        "id": len(scenes) + 1,
        "type": "follow",
        "headline": "THEO DÕI ĐỂ XEM THÊM",
        "text": "Bấm theo dõi kênh để cập nhật liên tục các tin tức nóng nhất.",
        "motion": "static",
    })

    # Đánh lại ID theo thứ tự
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
Hãy phân tích bài báo sau và tạo danh sách các scenes cho video thời sự dọc 9:16 ({duration} giây) theo đúng cấu trúc:
1. Scene 1: type="title_hero", headline="{title}" (giữ đầy đủ 100% tiêu đề bài báo, không được cắt ngắn), text="{title}" (CHỈ đọc đúng tiêu đề bài báo, không thêm câu dẫn nào khác).
2. Các Scene chi tiết: type="news_detail", mỗi scene là MỘT CÂU TRỌN VẸN duy nhất ngắn gọn dễ đọc, headline là cụm từ ngắn gọn (DIỄN BIẾN VỤ VIỆC, PHÁN QUYẾT CỦA TÒA ÁN...).
3. Scene cuối cùng: type="follow", headline="THEO DÕI ĐỂ XEM THÊM", text="Bấm theo dõi kênh để cập nhật nhiều tin hot."

BÀI BÁO:
Tiêu đề: {title}
Nguồn: {source}
Nội dung: {content[:3500]}

Trả về duy nhất định dạng JSON sau (KHÔNG bọc trong markdown ```json):
[
  {{
    "id": 1,
    "type": "title_hero",
    "headline": "{title}",
    "text": "Lời đọc mở đầu đầy đủ ý nghĩa.",
    "motion": "zoom_in"
  }},
  {{
    "id": 2,
    "type": "news_detail",
    "headline": "DIỄN BIẾN VỤ VIỆC",
    "text": "Một câu diễn biến chi tiết từ bài báo.",
    "motion": "pan"
  }},
  {{
    "id": 3,
    "type": "news_detail",
    "headline": "PHÁN QUYẾT CỦA TÒA ÁN",
    "text": "Một câu phán quyết mức án nghiêm minh.",
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
        model_candidates = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        resp = None
        for m in model_candidates:
            try:
                resp = client.models.generate_content(model=m, contents=prompt)
                if resp and resp.text:
                    print(f"Gemini successfully used model: {m}")
                    break
            except Exception as me:
                print(f"Model {m} failed: {me}")
                continue

        if not resp or not resp.text:
            return []

        raw = resp.text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'```$', '', raw).strip()
        scenes = json.loads(raw)
        return scenes
    except Exception as e:
        print(f"Gemini error: {e}")
        return []
