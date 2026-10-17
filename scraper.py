import re
from urllib.parse import urlparse, urljoin
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


def _get_article_images_from_html(soup: BeautifulSoup, base_url: str) -> list:
    """
    Cào hình ảnh từ VÙNG NỘI DUNG bài báo (article body), không lấy hình từ sidebar/header/footer.
    Ưu tiên thứ tự:
    1. Hình nằm trong thẻ article / .article-body / .content / .detail-content / figure
    2. Toàn bộ img còn lại trên trang (lọc hình nhỏ, icon, logo)
    """
    images = []
    skip_keywords = [
        '.svg', '.ico', 'logo', 'avatar', 'icon', 'banner', 'sprite',
        'button', 'ads', 'advertis', 'thumb_social', 'pixel', 'tracking',
        'facebook', 'twitter', 'zalo', 'share', 'related', 'widget',
        'nguonuutien', 'graphics', 'graphic', 'preference', 'google-news', 'follow_us',
        'userdeffault', 'userdefault', 'default_avatar', 'no-avatar', 'author', 'placeholder'
    ]

    # Các selector vùng nội dung bài báo phổ biến trên báo Việt Nam
    content_selectors = [
        'article',
        '[class*="article-body"]',
        '[class*="article-content"]',
        '[class*="detail-content"]',
        '[class*="post-content"]',
        '[class*="entry-content"]',
        '[class*="news-content"]',
        '[class*="article__body"]',
        '[class*="content-detail"]',
        '[class*="VnnContent"]',
        '[class*="fck_detail"]',
        '[id*="article-body"]',
        '[id*="article-content"]',
        '[id*="maincontent"]',
    ]

    # Tìm vùng nội dung bài báo
    content_area = None
    for selector in content_selectors:
        content_area = soup.select_one(selector)
        if content_area:
            break

    # Hàm trích xuất hình từ một vùng soup
    def extract_imgs_from_area(area):
        found = []
        for img in area.find_all("img"):
            # Các trang báo hiện đại (Vietnamnet, VnExpress, Dân Trí...) để ảnh thật trong data-original / data-src
            # còn thẻ src chỉ chứa ảnh rác 1x1 pixel base64: data:image/gif;base64,...
            src = (
                img.get("data-original") or
                img.get("data-src") or
                img.get("data-lazy-src") or
                img.get("data-full-src") or
                img.get("data-url") or
                img.get("data-srcset") or
                img.get("srcset") or
                img.get("src")
            )
            if not src:
                continue

            # Nếu là srcset dạng "url1 1x, url2 2x" hoặc "url 640w", bóc lấy url đầu tiên
            if "," in src and (" " in src or "w" in src or "x" in src):
                src = src.split(",")[0].strip().split(" ")[0].strip()

            # Bỏ qua ảnh base64 hoặc 1x1 pixel gif
            if src.startswith("data:image"):
                continue

            # Resolve relative URLs
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(base_url, src)

            # Bỏ qua các URL không phải http
            if not src.startswith("http"):
                continue

            # Bỏ qua icon/logo/quảng cáo
            src_lower = src.lower()
            if any(kw in src_lower for kw in skip_keywords):
                continue

            # Lọc theo kích thước nếu có attribute nhỏ (icon mũi tên, icon google news)
            w_attr = img.get("width", "")
            h_attr = img.get("height", "")
            try:
                if w_attr and int(str(w_attr).replace("px", "").strip()) < 100:
                    continue
                if h_attr and int(str(h_attr).replace("px", "").strip()) < 80:
                    continue
            except Exception:
                pass

            if src not in found:
                found.append(src)
        return found

    # Ưu tiên hình trong vùng nội dung bài báo
    if content_area:
        images = extract_imgs_from_area(content_area)

    # Nếu không đủ hình (< 2), thử lấy hình từ figure tags
    if len(images) < 2:
        for fig in soup.find_all("figure"):
            for img in fig.find_all("img"):
                src = (img.get("src") or img.get("data-src") or
                       img.get("data-lazy-src") or img.get("data-original"))
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        src = urljoin(base_url, src)
                    if src.startswith("http") and src not in images:
                        src_lower = src.lower()
                        if not any(kw in src_lower for kw in skip_keywords):
                            images.append(src)

    # Fallback: lấy toàn trang nếu vẫn không đủ hình
    if len(images) < 2:
        images = extract_imgs_from_area(soup)

    return images


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
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    html = ""
    session = requests.Session()
    try:
        resp = session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text

        # Bỏ qua thử thách JS cookie challenge của Cloudrity/WAF (ví dụ: Lao Động, Thanh Niên...)
        # document.cookie="D1N=64b19392795e66f6da64aa5e87191caa"; expires=...; window.location.reload(true);
        if "document.cookie" in html and "window.location.reload" in html:
            c_match = re.search(r'document\.cookie\s*=\s*["\']([^="\'\s]+)=([^;"\'\s]+)', html)
            if c_match:
                c_name, c_val = c_match.group(1), c_match.group(2)
                session.cookies.set(c_name, c_val, domain=urlparse(url).netloc)
                retry_resp = session.get(url, headers=headers, timeout=15)
                if retry_resp.status_code == 200 and len(retry_resp.text) > len(html):
                    html = retry_resp.text
    except Exception:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            html = downloaded

    title = ""
    images = []

    if html:
        soup = BeautifulSoup(html, "html.parser")

        # Lấy tiêu đề
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        # og:image ưu tiên đầu tiên (thường là hình đại diện bài báo)
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            og_src = og_img["content"]
            if og_src.startswith("//"):
                og_src = "https:" + og_src
            images.append(og_src)

        # Lấy hình từ vùng nội dung bài báo
        article_imgs = _get_article_images_from_html(soup, url)
        for src in article_imgs:
            if src not in images:
                images.append(src)

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


def extract_multiple_articles(urls: list) -> dict:
    """
    Cào nhiều bài báo từ danh sách URL (2-3 bài), gộp nội dung và ảnh lại.
    Trả về dict giống extract_article_content nhưng nội dung là tổng hợp từ tất cả bài.
    """
    all_contents = []
    all_images = []
    all_titles = []
    all_sources = []

    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            article = extract_article_content(url)
            if article.get("title"):
                all_titles.append(article["title"])
            if article.get("content") and len(article["content"].strip()) > 20:
                all_contents.append(f"--- BÀI {len(all_contents)+1}: {article.get('title', '')} ---\n{article['content']}")
            if article.get("source"):
                all_sources.append(article["source"])
            for img in article.get("images", []):
                if img not in all_images:
                    all_images.append(img)
        except Exception as e:
            print(f"[scraper] Lỗi cào bài {url}: {e}")
            continue

    if not all_contents:
        raise Exception("Không cào được nội dung từ bất kỳ link nào trong danh sách.")

    # Gộp tiêu đề: Lấy tiêu đề bài đầu tiên làm tiêu đề chính
    merged_title = all_titles[0] if all_titles else "Tổng hợp tin tức"
    merged_source = " + ".join(list(dict.fromkeys(all_sources))) if all_sources else "Tổng hợp"
    merged_content = "\n\n".join(all_contents)

    return {
        "title": merged_title,
        "content": merged_content,
        "source": merged_source,
        "url": urls[0] if urls else None,
        "images": all_images,
        "article_count": len(all_contents),
    }
