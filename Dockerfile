FROM python:3.13-slim

# Cài đặt FFmpeg và font chữ hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-freefont-ttf \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục làm việc
WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Copy và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn
COPY . .

# Tạo các thư mục cần thiết
RUN mkdir -p outputs assets static

# Cổng mặc định cho Render / Cloud
ENV PORT=10000
EXPOSE 10000

# Khởi chạy ứng dụng
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
