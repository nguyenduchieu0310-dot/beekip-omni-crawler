import io
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf  # PyMuPDF
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("beekip.derivative")

# Giới hạn dung lượng theo Tiêu chuẩn Mục 3.1
MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
RECOMMENDED_PDF_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_PAGE_COUNT = 1500
MIN_PAGE_COUNT = 1
MIN_CHARS_PER_TEXT_PAGE = 150

# Giới hạn ảnh bìa theo Tiêu chuẩn Mục 3.2
MIN_COVER_WIDTH_PX = 1200
MAX_COVER_SIZE_BYTES = 250 * 1024  # 250 KB
RECOMMENDED_COVER_QUALITY = 84

# Các Action mã độc cần quét trong cấu trúc PDF
DANGEROUS_PDF_OBJECTS = [
    b"/JavaScript",
    b"/JS",
    b"/Launch",
    b"/EmbeddedFiles",
]

class DerivativeRendererEngine:
    """Engine kiểm chuẩn tệp phái sinh PDF và render ảnh bìa Thumbnail chuẩn Google Discover.
    Tuân thủ nghiêm ngặt tiêu chuẩn BEEKIP-DOC-STD-2026 Mục 3.1 & Mục 3.2.
    """

    def __init__(self):
        pass

    def validate_pdf_standards(self, pdf_path: Path) -> Dict[str, Any]:
        """Kiểm tra toàn bộ 7 tiêu chí tệp phái sinh PDF theo Mục 3.1."""
        if not pdf_path.exists():
            return {"valid": False, "error": f"Tệp không tồn tại: {pdf_path}"}

        file_size = pdf_path.stat().st_size
        results: Dict[str, Any] = {
            "valid": True,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "size_pass": file_size <= MAX_PDF_SIZE_BYTES,
            "page_count": 0,
            "page_count_pass": False,
            "has_consecutive_blank_pages": False,
            "has_searchable_text": False,
            "avg_chars_per_page": 0,
            "mojibake_detected": False,
            "malware_free": True,
            "malware_findings": [],
            "reasons": []
        }

        # 1. Kiểm tra kích thước file
        if not results["size_pass"]:
            results["valid"] = False
            results["reasons"].append(f"Dung lượng vượt quá 50MB ({results['file_size_mb']} MB)")

        try:
            doc = pymupdf.open(str(pdf_path))
            page_count = len(doc)
            results["page_count"] = page_count
            results['pdf_version'] = doc.metadata.get('format', '')
            valid_pdf_versions = ('PDF 1.3', 'PDF 1.4', 'PDF 1.5', 'PDF 1.6', 'PDF 1.7', 'PDF 2.0')
            if results['pdf_version'] and results['pdf_version'] not in valid_pdf_versions:
                results['valid'] = False
                results['reasons'].append(f'Unsupported PDF version: {results["pdf_version"]}')

            # 2. Kiểm tra số trang
            results["page_count_pass"] = (MIN_PAGE_COUNT <= page_count <= MAX_PAGE_COUNT)
            if not results["page_count_pass"]:
                results["valid"] = False
                results["reasons"].append(f"Số trang không hợp lệ: {page_count} (chỉ chấp nhận từ 1 đến 1500 trang)")

            # 3. Quét từng trang: text layer, trang trắng, mojibake
            total_chars = 0
            consecutive_blanks = 0
            max_consecutive_blanks = 0
            pages_with_insufficient_text = 0

            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text() or ""
                normalized_text = unicodedata.normalize("NFC", text)
                char_count = len(normalized_text.strip())
                total_chars += char_count
                is_ending_page = (page_num == page_count - 1 and char_count >= 20)
                has_page_media = (len(page.get_images()) > 0 or len(page.get_drawings()) > 0)
                if char_count < MIN_CHARS_PER_TEXT_PAGE and not has_page_media and not is_ending_page:
                    pages_with_insufficient_text += 1

                # Kiểm tra mojibake (chuỗi lỗi font \uFFFD)
                if "\uFFFD" in normalized_text:
                    results["mojibake_detected"] = True

                # Kiểm tra trang trắng liên tiếp (không có chữ và không có hình ảnh/bản vẽ)
                is_blank = (char_count < 25 and len(page.get_images()) == 0 and len(page.get_drawings()) == 0)
                if is_blank:
                    consecutive_blanks += 1
                    max_consecutive_blanks = max(max_consecutive_blanks, consecutive_blanks)
                else:
                    consecutive_blanks = 0

            results["has_consecutive_blank_pages"] = (max_consecutive_blanks > 1)
            if results["has_consecutive_blank_pages"]:
                results["valid"] = False
                results["reasons"].append(f"Có {max_consecutive_blanks} trang trắng liên tiếp")

            avg_chars = round(total_chars / max(1, page_count), 1)
            results["avg_chars_per_page"] = avg_chars
            # Lớp chữ tìm kiếm: mọi trang văn bản đều phải có chữ hoặc hình ảnh học thuật
            results["has_searchable_text"] = (page_count > 0 and pages_with_insufficient_text == 0)
            if not results["has_searchable_text"]:
                results["valid"] = False
                results["reasons"].append(f"Thiếu Text Layer tìm kiếm (trung bình chỉ có {avg_chars} ký tự/trang)")

            if results["mojibake_detected"]:
                results["valid"] = False
                results["reasons"].append("Phát hiện ký tự lỗi font cổ/mojibake (\uFFFD)")

            # Inspect decompressed PDF objects as well as the raw file.
            for xref in range(1, doc.xref_length()):
                try:
                    object_text = doc.xref_object(xref, compressed=False).encode('latin1', errors='replace')
                    for dangerous in DANGEROUS_PDF_OBJECTS:
                        if dangerous in object_text:
                            results['malware_findings'].append(dangerous.decode('latin1'))
                except Exception:
                    continue
            doc.close()

            # 4. Quét mã độc (Malware AST check)
            with open(pdf_path, "rb") as f:
                raw_bytes = f.read()
                for dangerous in DANGEROUS_PDF_OBJECTS:
                    if dangerous in raw_bytes:
                        results["malware_findings"].append(dangerous.decode("latin1"))

            if results["malware_findings"]:
                results["malware_free"] = False
                results["valid"] = False
                results["reasons"].append(f"Phát hiện cấu trúc nhúng khả nghi: {', '.join(results['malware_findings'])}")

        except Exception as e:
            logger.error("Lỗi khi kiểm tra PDF %s: %s", pdf_path, e)
            results["valid"] = False
            results["reasons"].append(f"Lỗi phân tích cú pháp PDF: {str(e)}")

        return results

    def render_cover_thumbnail(
        self,
        pdf_path: Path,
        output_image_path: Path,
        target_width: int = MIN_COVER_WIDTH_PX,
        quality: int = RECOMMENDED_COVER_QUALITY,
        format_type: str = "JPEG"
    ) -> Dict[str, Any]:
        """Render trang 1 của PDF phái sinh thành ảnh bìa Thumbnail đạt chuẩn Google Discover (Mục 3.2)."""
        if not pdf_path.exists():
            return {"success": False, "error": f"Tệp PDF không tồn tại: {pdf_path}"}

        output_image_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            doc = pymupdf.open(str(pdf_path))
            if len(doc) == 0:
                doc.close()
                return {"success": False, "error": "Tệp PDF không có trang nào để render bìa"}

            # Render trang 1 với dpi đủ cao để đảm bảo width >= 1200px
            page = doc[0]
            # Tính zoom factor để đạt target_width
            rect = page.rect
            orig_w = rect.width
            zoom = max(1.5, (target_width / max(1, orig_w)))
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            doc.close()

            # Chuyển đổi sang PIL Image để tối ưu hóa nén
            img_bytes = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_bytes))

            # Resize chính xác theo target_width nếu cần
            if img.width != target_width:
                aspect = img.height / img.width
                target_height = int(target_width * aspect)
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # Chuyển RGB chuẩn
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Lưu và kiểm soát dung lượng <= 250 KB. Dense exam pages can remain
            # above the limit at quality 70, so continue down to 30 while keeping
            # the required 1200px width.
            current_quality = quality
            encoded = None
            for current_quality in range(quality, 29, -6):
                buffer = io.BytesIO()
                img.save(buffer, format=format_type, quality=current_quality,
                         optimize=True, progressive=True, subsampling=2)
                size = buffer.tell()
                encoded = buffer.getvalue()
                if size <= MAX_COVER_SIZE_BYTES:
                    break
            with open(output_image_path, "wb") as f_out:
                f_out.write(encoded or b'')

            final_size = output_image_path.stat().st_size
            w, h = img.size

            return {
                "success": True,
                "output_image_path": str(output_image_path),
                "width_px": w,
                "height_px": h,
                "aspect_ratio": round(w / h, 3),
                "file_size_bytes": final_size,
                "file_size_kb": round(final_size / 1024, 1),
                "quality_used": current_quality,
                "meets_google_discover": (w >= MIN_COVER_WIDTH_PX and final_size <= MAX_COVER_SIZE_BYTES)
            }
        except Exception as e:
            logger.error("Lỗi khi render ảnh bìa cho %s: %s", pdf_path, e)
            return {"success": False, "error": str(e)}
