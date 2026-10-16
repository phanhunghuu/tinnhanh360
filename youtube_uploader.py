"""
Module upload video to YouTube Data API v3 (Shorts support)
"""
import os
import json
import socket
from typing import Optional, Dict

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

BASE_DIR = os.path.dirname(__file__)
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "client_secrets.json")
TOKEN_FILE = os.path.join(BASE_DIR, "youtube_token.json")


def is_youtube_configured() -> bool:
    """Kiểm tra xem file client_secrets.json đã có chưa."""
    return os.path.exists(CLIENT_SECRETS_FILE)


def is_youtube_authenticated() -> bool:
    """Kiểm tra xem token đã được cấp và còn hợp lệ không."""
    if not os.path.exists(TOKEN_FILE):
        return False
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        return bool(creds and (creds.valid or creds.refresh_token))
    except Exception:
        return False


def get_youtube_credentials(open_browser: bool = True) -> Credentials:
    """Lấy credentials, nếu hết hạn thì tự refresh hoặc mở OAuth flow."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                raise FileNotFoundError(
                    "Không tìm thấy file client_secrets.json! Vui lòng tải từ Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES
            )
            # Chạy local server trên cổng ngẫu nhiên khả dụng để nhận callback từ Google
            creds = flow.run_local_server(
                port=0,
                prompt='consent',
                access_type='offline',
                open_browser=open_browser
            )

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[list] = None,
    privacy_status: str = "public"
) -> Dict:
    """
    Tải video lên YouTube Shorts.
    - video_path: Đường dẫn tuyệt đối đến file MP4
    - title: Tiêu đề video (tự động gắn thêm #Shorts nếu chưa có)
    - description: Mô tả chi tiết
    - privacy_status: 'public', 'unlisted', hoặc 'private'
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

    # Chuẩn hoá tiêu đề cho YouTube Shorts (tối đa 100 ký tự)
    clean_title = title.strip()
    if "#Shorts" not in clean_title and "#shorts" not in clean_title:
        clean_title = f"{clean_title} #Shorts"
    if len(clean_title) > 100:
        clean_title = clean_title[:92].strip() + " #Shorts"

    default_tags = ["Tin tức", "Tin nóng 24h", "Thời sự", "Shorts", "Tin nhanh"]
    if tags:
        default_tags = list(set(default_tags + tags))

    if not description:
        description = f"{title}\n\nCập nhật tin tức nhanh chóng & chính xác.\n#Shorts #tintuc24h #thoisu"

    creds = get_youtube_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": clean_title,
            "description": description,
            "tags": default_tags,
            "categoryId": "25",  # Category 25 = News & Politics
            "defaultLanguage": "vi",
            "defaultAudioLanguage": "vi",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        }
    }

    # Upload dạng Resumable MediaUpload
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 4  # 4MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()

    video_id = response.get("id")
    video_url = f"https://www.youtube.com/shorts/{video_id}"

    return {
        "success": True,
        "video_id": video_id,
        "video_url": video_url,
        "title": clean_title,
        "privacy": privacy_status
    }
