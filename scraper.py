import re
from urllib.parse import urlparse
import requests
import trafilatura
from bs4 import BeautifulSoup

def extract_domain_name(url: str) -> str:
    try:
        domain = urlparse(url).netloc
        domain = re.sub(r'^www\.', '', domain)
        return domain
    except Exception:
        return "Nguồn tin"

def extract_article_content(url_or_text: str):
    """
    Nhận vào URL bài báo hoặc đoạn văn bản.
    Trả về dict: { "title": str, "content": str, "source": str, "images": list }
    """
    if not (url_or_text.strip().startswith("http://") or url_or_text.strip().startswith("https://")):
        lines = [l.strip() for l in url_or_text.strip().split("\n") if l.strip()]
        title = lines[0] if lines else "Tin tức tổng hợp"
        content = "\n".join(lines[1:]) if len(lines) > 1 else title
        return {
            "title": title[:100],
            "content": content,
            "source": "Bản tin",
            "url": None,
            "images": []
        }

    url = url_or_text.strip()
    source_name = extract_domain_name(url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    html = ""
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        html = resp.text
    except Exception:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            html = downloaded

    title = ""
    images = []

    if html:
        soup = BeautifulSoup(html, "html.parser")
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            images.append(og_img["content"])
            
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http") and not any(ext in src.lower() for ext in ['.svg', '.ico', 'logo', 'avatar']):
                if src not in images:
                    images.append(src)
                if len(images) >= 5:
                    break

    text_content = trafilatura.extract(html, include_comments=False, include_tables=False) if html else None
    if not text_content:
        if html:
            paragraphs = soup.find_all('p')
            text_content = "\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
        else:
            text_content = "Không thể đọc nội dung từ link bài báo này."

    return {
        "title": title or "Tin tức mới cập nhật",
        "content": text_content,
        "source": source_name,
        "url": url,
        "images": images
    }
