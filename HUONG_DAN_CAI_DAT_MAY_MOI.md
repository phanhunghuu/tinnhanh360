# 📖 HƯỚNG DẪN CÀI ĐẶT & CHUYỂN DỜI HỆ THỐNG TIN NHANH 360 SANG MÁY MỚI

Tài liệu này giúp bất kỳ ai khi copy thư mục dự án hoặc clone repo sang một máy tính mới (Windows, macOS hoặc Linux) đều có thể cài đặt đầy đủ tất cả thư viện và chạy hệ thống mượt mà chỉ trong vài phút.

---

## 🛠️ YÊU CẦU TIÊN QUYẾT (TRÊN MÁY TÍNH MỚI)

1. **Python**: Khuyến nghị phiên bản **3.10, 3.11, 3.12 hoặc 3.13** (Khi cài đặt trên Windows, **BẮT BUỘC** tích chọn ô `Add python.exe to PATH`).
2. **Git**: Đã cài đặt Git ([git-scm.com](https://git-scm.com/)).
3. **FFmpeg**: Công cụ dựng và xử lý video/audio (bắt buộc).
   - **Windows**: Mở PowerShell chạy: `winget install Gyan.FFmpeg` (hoặc tải ffmpeg giải nén và thêm vào biến môi trường Path).
   - **macOS**: Chạy terminal: `brew install ffmpeg`
   - **Linux/Ubuntu**: Chạy terminal: `sudo apt update && sudo apt install -y ffmpeg`

---

## 🚀 CÁCH CÀI ĐẶT NHANH NHẤT (WINDOWS - 1 CLICK)

Nếu máy tính mới chạy **Windows**, bạn chỉ cần:

1. Click đúp chuột vào file: **`install.bat`**
   - File này sẽ tự động:
     - Tạo môi trường ảo `venv`
     - Cài toàn bộ thư viện cần thiết trong `requirements.txt`
     - Tự động clone & liên kết thư viện giọng đọc chân thực `Kokoro-Vietnamese`
     - Tải sẵn mô hình AI Kokoro về máy.
2. Sau khi cài xong, mỗi lần muốn mở app chỉ cần click đúp chuột vào: **`run.bat`**
3. Mở trình duyệt web truy cập: **`http://localhost:8000`**

---

## 💻 CÁCH CÀI ĐẶT THỦ CÔNG (CHO WINDOWS, MAC & LINUX)

Nếu bạn muốn tự gõ lệnh trong Terminal / PowerShell:

### Bước 1: Mở Terminal tại thư mục dự án và tạo môi trường ảo

- **Trên Windows (cmd / PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
- **Trên macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### Bước 2: Cài đặt toàn bộ thư viện hệ thống
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 3: Cài đặt gói giọng đọc AI Kokoro-Vietnamese
```bash
# Clone repo Kokoro-Vietnamese nếu chưa có:
git clone https://github.com/iamdinhthuan/Kokoro-Vietnamese.git Kokoro-Vietnamese

# Cài đặt liên kết trực tiếp vào môi trường:
cd Kokoro-Vietnamese
pip install -e . --no-deps
cd ..
```

### Bước 4: Khởi động hệ thống
```bash
python main.py
```
Sau đó truy cập: `http://localhost:8000`

---

## 🔑 CÁC FILE CẤU HÌNH CẦN CHÚ Ý KHI CHUYỂN MÁY

1. **`client_secrets.json`**: Nếu cần tính năng tải tự động lên kênh YouTube, hãy copy file `client_secrets.json` tải từ Google Cloud Console đặt vào thư mục gốc.
2. **Key AI (Groq / Gemini)**: Hệ thống đã tích hợp sẵn key dự phòng, hoặc bạn có thể điền API key cá nhân trực tiếp tại ô nhập trên giao diện web.
