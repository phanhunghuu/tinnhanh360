@echo off
title AI News Video Maker Pro
chcp 65001 >nul
echo ========================================================
echo        AI NEWS VIDEO MAKER PRO - KHỞI ĐỘNG LOCAL
echo ========================================================
echo.

cd /d "%~dp0"

REM Kiểm tra môi trường ảo
if not exist "venv\Scripts\activate.bat" (
    echo [!] Chưa tìm thấy môi trường ảo venv. Đang tạo mới...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [*] Đang cài đặt thư viện...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo [*] Đang khởi chạy máy chủ tại http://127.0.0.1:8000 ...
echo [*] Bạn có thể mở trình duyệt và truy cập: http://127.0.0.1:8000
echo.

start http://127.0.0.1:8000
python main.py

pause
