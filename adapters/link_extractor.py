import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from adapters.base_adapter import DownloadCandidate

GDRIVE_REGEX = re.compile(
    r'https?://(?:drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)|docs\.google\.com/(?:document/d/|presentation/d/|spreadsheets/d/))([a-zA-Z0-9_-]+)'
)

DIRECT_FILE_REGEX = re.compile(r'\.(pdf|docx|doc|pptx|ppt)(?:\?.*)?$', re.IGNORECASE)
IMAGE_FILE_REGEX = re.compile(r'\.(jpe?g|png|gif|webp|svg|bmp|ico|tiff|avif)(?:\?.*)?$', re.IGNORECASE)

def extract_candidates_from_html(page_url: str, html: str) -> List[DownloadCandidate]:
    """
    Extract all viable PDF/Word/PowerPoint download links from HTML content.
    Strictly discards images and non-document formats.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    candidates: List[DownloadCandidate] = []
    seen_urls = set()

    def add_candidate(target_url: str, text: str = ""):
        cleaned_url = target_url.strip()
        # Fix malformed URLs with leading slash before protocol (e.g. /https://file.kenhgiaovien.com/...)
        cleaned_url = re.sub(r'^/+(https?://)', r'\1', cleaned_url)
        full_url = urljoin(page_url, cleaned_url)
        full_url = re.sub(r'^https?://[^/]+/+(https?://)', r'\1', full_url)
        if full_url in seen_urls:
            return

        lower_url = full_url.lower()

        # STRICT REJECTION: Reject all standalone images and graphic media
        if IMAGE_FILE_REGEX.search(lower_url):
            return

        # Ignore external software or social platforms
        if any(ign in lower_url for ign in ["geogebra.org", "facebook.com", "zalo.me", "youtube.com", "tiktok.com"]):
            return

        is_gdrive = bool(GDRIVE_REGEX.search(full_url))

        # Classify document type strictly among PDF, Word, PowerPoint
        file_type = "PDF"
        if ".docx" in lower_url:
            file_type = "DOCX"
        elif ".doc" in lower_url:
            file_type = "DOC"
        elif ".pptx" in lower_url:
            file_type = "PPTX"
        elif ".ppt" in lower_url:
            file_type = "PPT"
        elif ".zip" in lower_url:
            file_type = "ZIP"

        # Check if URL directly points to document or Google Drive
        is_direct = bool(DIRECT_FILE_REGEX.search(lower_url))
        is_download_btn = any(kw in text.lower() for kw in ["tải", "download", "link tải", "xem tài liệu", "đính kèm"])

        if is_gdrive or is_direct or (is_download_btn and ("drive" in lower_url or "download" in lower_url)):
            seen_urls.add(full_url)
            candidates.append(
                DownloadCandidate(
                    url=full_url,
                    source_url=page_url,
                    file_type=file_type,
                    file_name=None,
                    is_direct_cdn=is_direct,
                    is_gdrive=is_gdrive
                )
            )

    # 1. Search anchor tags
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)
        if href and not href.startswith("#") and not href.startswith("javascript:"):
            add_candidate(href, text)

    # 2. Search iframes (Google Drive previews)
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"].strip()
        if "drive.google.com" in src or "docs.google.com" in src:
            add_candidate(src, "iframe drive")

    return candidates
