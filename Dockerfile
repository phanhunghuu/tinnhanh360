FROM python:3.11-slim

# Cài đặt FFmpeg và font chữ hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-freefont-ttf \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục làm việc
WORKDIR /app

# Copy và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn
COPY . .

# Tạo các thư mục cần thiết nếu chưa có
RUN mkdir -p outputs assets static

# Cổng mặc định của Hugging Face Spaces là 7860
EXPOSE 7860

# Khởi chạy ứng dụng trên cổng 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
