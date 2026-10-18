@echo off
chcp 65001 >nul
echo ========================================================
echo   CÀI ĐẶT TỰ ĐỘNG HỆ THỐNG TIN NHANH 360 (CHO MÁY MỚI)
echo ========================================================
echo.

:: 1. Kiểm tra Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [LỖI] Máy tính chưa cài đặt Python!
    echo Vui lòng cài Python 3.10, 3.11 hoặc 3.12 từ https://www.python.org/ (Nhớ tick chọn 'Add python.exe to PATH').
    pause
    exit /b 1
)

:: 2. Kiểm tra FFmpeg
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo [CẢNH BÁO] Chưa tìm thấy FFmpeg trong PATH hệ thống.
    echo Bạn có thể cài nhanh bằng lệnh PowerShell: winget install Gyan.FFmpeg
    echo.
)

:: 3. Tạo môi trường ảo venv nếu chưa có
if not exist "venv" (
    echo [1/4] Đang khởi tạo môi trường ảo Python (venv)...
    python -m venv venv
) else (
    echo [1/4] Môi trường ảo (venv) đã tồn tại.
)

:: 4. Nâng cấp pip và cài đặt requirements.txt
echo [2/4] Đang nâng cấp pip và cài đặt các thư viện từ requirements.txt...
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt

:: 5. Cài đặt Kokoro-Vietnamese
echo [3/4] Đang chuẩn bị mô hình giọng đọc chân thực Kokoro-Vietnamese...
if not exist "Kokoro-Vietnamese" (
    echo Đang clone Kokoro-Vietnamese từ GitHub...
    git clone https://github.com/iamdinhthuan/Kokoro-Vietnamese.git Kokoro-Vietnamese
)

echo Đang liên kết thư viện Kokoro-Vietnamese vào môi trường venv...
cd Kokoro-Vietnamese
..\venv\Scripts\pip.exe install -e . --no-deps
cd ..

:: 6. Tải sẵn mô hình và giọng đọc phổ biến
echo [4/4] Đang kiểm tra và tải trọng số mô hình Kokoro AI...
.\venv\Scripts\python.exe -c "import soundfile, kokoro_vietnamese; from kokoro_vietnamese import KokoroVietnamese; tts = KokoroVietnamese(device='cpu', voice='hung_thinh'); print('Kokoro AI đã sẵn sàng!')"

echo.
echo ========================================================
echo   CHÚC MỪNG: CÀI ĐẶT THÀNH CÔNG 100%!
echo   Để khởi chạy ứng dụng, bạn chỉ cần chạy: run.bat
echo ========================================================
echo.
pause
