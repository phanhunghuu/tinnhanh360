# AI News Video Maker Pro

Dự án tự động chuyển đổi bài báo thành video ngắn dạng dọc 9:16 (TikTok, Reels, Shorts) theo chuẩn đồ họa thời sự.

## 🚀 Cách chạy dự án

### 1. Cài đặt FFmpeg (bắt buộc)
- Trên macOS:
  ```bash
  brew install ffmpeg
  ```
- Trên Windows: Tải từ trang chủ FFmpeg hoặc cài qua winget: `winget install Gyan.FFmpeg`
- Trên Linux: `sudo apt update && sudo apt install ffmpeg`

### 2. Cài đặt môi trường Python (Khuyến nghị Python 3.10+)
```bash
# Tạo môi trường ảo
python3 -m venv venv

# Kích hoạt môi trường ảo:
# Trên macOS / Linux:
source venv/bin/activate
# Trên Windows:
venv\Scripts\activate

# Cài đặt các thư viện cần thiết:
pip install -r requirements.txt
```

### 3. Khởi chạy ứng dụng
```bash
python main.py
```
Mở trình duyệt truy cập: `http://127.0.0.1:8000`

---

## 📁 Cấu trúc thư mục

- `main.py`: Khởi chạy FastAPI backend và API endpoints.
- `scraper.py`: Trích xuất tiêu đề, nội dung, ảnh minh họa từ link bài báo.
- `script_generator.py`: Tách bài viết thành các phân cảnh thời sự mạch lạc.
- `overlay_renderer.py`: Tạo các lớp phủ hình ảnh, badge, tiêu đề, logo đỏ/trắng và frame theo dõi.
- `video_pipeline.py`: Xử lý ffmpeg zoompan, căn chuẩn tỷ lệ 9:16 và ghép video hoàn chỉnh.
- `tts.py`: Chuyển đổi văn bản thành giọng đọc thời sự Edge-TTS.
- `assets/`: Chứa logo đỏ, trắng và hình ảnh frame outro follow.
- `fonts/`: Chứa font chữ Inter-Bold chuẩn TV.
- `static/`: Giao diện web người dùng.
