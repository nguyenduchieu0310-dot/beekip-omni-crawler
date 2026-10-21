import hashlib
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse
import requests

from core.config import (
    DEFAULT_USER_AGENT,
    DOWNLOADS_PDF_DIR,
    DOWNLOADS_WORD_DIR,
    DOWNLOADS_PPT_DIR,
    ALLOWED_DOC_EXTENSIONS,
    DISALLOWED_IMAGE_EXTENSIONS,
)
from core.rate_limiter import global_rate_limiter

logger = logging.getLogger("beekip.downloader")

GDRIVE_ID_REGEX = re.compile(
    r'(?:drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)|docs\.google\.com/(?:document|presentation|spreadsheets)/d/)([a-zA-Z0-9_-]{20,})'
)

@dataclass
class DownloadedFileResult:
    file_path: Path
    sha256_hash: str
    file_size_bytes: int
    mime_type: str
    original_filename: str
    source_url: str

class ResilientFileDownloader:
    """Downloads documents from Google Drive or direct CDN links with stream hashing & retries."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.last_failure_code: Optional[str] = None

    def download(
        self,
        url: str,
        dest_dir: Optional[Path] = None,
        preferred_name: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[DownloadedFileResult]:
        """Download file and return file details with SHA-256 hash."""
        self.last_failure_code = None
        domain = global_rate_limiter.extract_domain(url)
        global_rate_limiter.wait_if_needed(domain)

        # Check if Google Drive link
        gdrive_match = GDRIVE_ID_REGEX.search(url)
        if gdrive_match:
            file_id = gdrive_match.group(1)
            return self._download_gdrive(file_id, url, dest_dir, preferred_name, max_retries)

        return self._download_direct(url, dest_dir, preferred_name, max_retries)

    def _download_gdrive(
        self,
        file_id: str,
        original_url: str,
        dest_dir: Optional[Path],
        preferred_name: Optional[str],
        max_retries: int
    ) -> Optional[DownloadedFileResult]:
        """Download file from Google Drive handling large file confirmation cookies."""
        download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0"

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(download_url, stream=True, timeout=30)

                # Check if Google returned HTML confirmation page for large files
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    # Look for confirmation token
                    html = resp.text
                    confirm_token = None
                    token_match = re.search(r'confirm=([0-9A-Za-z_]+)', html)
                    if token_match:
                        confirm_token = token_match.group(1)
                    elif "download_warning" in html:
                        confirm_token = "t"

                    if confirm_token:
                        confirmed_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={confirm_token}&authuser=0"
                        resp = self.session.get(confirmed_url, stream=True, timeout=40)

                if resp.status_code == 200:
                    return self._save_stream_to_disk(resp, original_url, dest_dir, preferred_name)
                elif resp.status_code in (404, 403, 410):
                    logger.warning("GDrive download unrecoverable status %s for file_id %s", resp.status_code, file_id)
                    self.last_failure_code = 'UNAVAILABLE_DOCUMENT'
                    return None

                logger.warning("GDrive download status %s for file_id %s (attempt %s)", resp.status_code, file_id, attempt)
            except Exception as e:
                logger.error("Error downloading from GDrive %s (attempt %s): %s", file_id, attempt, e)

            time.sleep(2.0 * attempt)

        self.last_failure_code = 'TRANSIENT_DOWNLOAD_FAILED'
        return None

    def _download_direct(
        self,
        url: str,
        dest_dir: Optional[Path],
        preferred_name: Optional[str],
        max_retries: int
    ) -> Optional[DownloadedFileResult]:
        """Download file from direct CDN URL, strictly rejecting standalone images."""
        url_lower = url.lower()
        if any(url_lower.endswith(ext) or f"{ext}?" in url_lower for ext in DISALLOWED_IMAGE_EXTENSIONS):
            logger.info("Chặn tải tệp ảnh: %s", url)
            self.last_failure_code = 'IMAGE_REJECTED'
            return None

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(url, stream=True, timeout=35)
                content_type = resp.headers.get("Content-Type", "").lower()
                if content_type.startswith("image/"):
                    logger.info("Chặn tải tệp do Content-Type là ảnh (%s): %s", content_type, url)
                    self.last_failure_code = 'IMAGE_REJECTED'
                    return None

                if resp.status_code == 200:
                    return self._save_stream_to_disk(resp, url, dest_dir, preferred_name)
                elif resp.status_code in (404, 403, 410):
                    logger.warning("Direct download unrecoverable status %s: %s", resp.status_code, url)
                    self.last_failure_code = 'UNAVAILABLE_DOCUMENT'
                    return None

                logger.warning("Direct download failed %s status %s (attempt %s)", url, resp.status_code, attempt)
            except Exception as e:
                logger.error("Error direct downloading %s (attempt %s): %s", url, attempt, e)

            time.sleep(2.0 * attempt)

        self.last_failure_code = 'TRANSIENT_DOWNLOAD_FAILED'
        return None

    def _save_stream_to_disk(
        self,
        resp: requests.Response,
        source_url: str,
        dest_dir: Optional[Path],
        preferred_name: Optional[str]
    ) -> Optional[DownloadedFileResult]:
        content_type = resp.headers.get("Content-Type", "").lower()
        if content_type.startswith("image/"):
            logger.info("Chặn lưu tệp do Content-Type là ảnh (%s): %s", content_type, source_url)
            self.last_failure_code = 'IMAGE_REJECTED'
            return None

        content_disposition = resp.headers.get("Content-Disposition", "")
        filename = preferred_name

        if not filename and "filename=" in content_disposition:
            match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition)
            if match:
                filename = match.group(1).strip()

        if not filename:
            path_part = urlparse(source_url).path.split("/")[-1]
            filename = path_part if path_part and "." in path_part else ""

        # Strictly check for image files and reject
        fn_lower = filename.lower()
        if any(fn_lower.endswith(ext) for ext in DISALLOWED_IMAGE_EXTENSIONS):
            logger.info("Chặn lưu tệp ảnh: %s", filename)
            self.last_failure_code = 'IMAGE_REJECTED'
            return None

        # Classify into 3 canonical educational document formats: PDF, Word, PowerPoint
        is_word = fn_lower.endswith((".docx", ".doc"))
        is_ppt = fn_lower.endswith((".pptx", ".ppt"))
        is_pdf = fn_lower.endswith(".pdf")

        if not (is_word or is_ppt or is_pdf):
            if "pdf" in content_type:
                filename = (filename or "document") + ".pdf"
                is_pdf = True
            elif "word" in content_type or "officedocument.wordprocessingml" in content_type or "msword" in content_type:
                filename = (filename or "document") + ".docx"
                is_word = True
            elif "powerpoint" in content_type or "presentation" in content_type:
                filename = (filename or "document") + ".pptx"
                is_ppt = True
            else:
                # Do NOT save HTML pages or unknown binary files as documents
                logger.info("Bỏ qua tệp không thuộc 3 loại tài liệu (PDF, Word, PPT): %s (Content-Type: %s)", filename, content_type)
                self.last_failure_code = 'UNSUPPORTED_FILE_TYPE'
                return None

        # Route to appropriate directory and mime-type
        if is_word:
            target_dir = dest_dir or DOWNLOADS_WORD_DIR
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if filename.lower().endswith(".docx") else "application/msword"
        elif is_ppt:
            target_dir = dest_dir or DOWNLOADS_PPT_DIR
            mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation" if filename.lower().endswith(".pptx") else "application/vnd.ms-powerpoint"
        else:
            target_dir = dest_dir or DOWNLOADS_PDF_DIR
            mime_type = "application/pdf"

        target_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        file_path = target_dir / safe_filename

        # If file exists, add timestamp prefix
        if file_path.exists():
            file_path = target_dir / f"{int(time.time())}_{safe_filename}"

        hasher = hashlib.sha256()
        total_bytes = 0

        try:
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        total_bytes += len(chunk)
                        if total_bytes > 50 * 1024 * 1024:
                            raise ValueError('Document exceeds the 50 MiB limit')
                        hasher.update(chunk)
                        f.write(chunk)
        except Exception:
            file_path.unlink(missing_ok=True)
            raise
        finally:
            resp.close()

        # File extensions and HTTP headers alone do not identify a PDF.
        if mime_type == 'application/pdf':
            with file_path.open('rb') as stream:
                valid_header = stream.read(5) == b'%PDF-'
            if not valid_header:
                file_path.unlink(missing_ok=True)
                self.last_failure_code = 'INVALID_PDF'
                return None

        return DownloadedFileResult(
            file_path=file_path,
            sha256_hash=hasher.hexdigest(),
            file_size_bytes=total_bytes,
            mime_type=mime_type,
            original_filename=safe_filename,
            source_url=source_url
        )
