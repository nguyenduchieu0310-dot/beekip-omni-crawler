import io
import logging
import os
import re
import zipfile
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

_LOCAL_DEPS = Path(r"D:\Codex\Projects\Beekip.vn\tmp\crawler-test-deps-20261017")
if _LOCAL_DEPS.exists() and str(_LOCAL_DEPS) not in sys.path:
    sys.path.insert(0, str(_LOCAL_DEPS))

import pymupdf  # PyMuPDF

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("beekip.sanitizer")

# ==============================================================================
# 1. REGEX SPECIFICATIONS (BEEKIP-DOC-STD-2026 MỤC 3.3)
# ==============================================================================

# Số điện thoại, Hotline, Zalo có tiền tố
PHONE_PREFIXED_REGEX = re.compile(
    r'(?i)(?:sđt|đt|điện thoại|hotline|zalo|liên hệ|mua file word|mua đề|tư vấn|phone|tel)[\s:]*(?:\+84|0)(?:[\s\.\-]?[0-9]){8,11}\b',
    re.IGNORECASE
)

# Số điện thoại độc lập trong header/footer/lề
PHONE_STANDALONE_REGEX = re.compile(
    r'\b(?:\+84|0)[1-9](?:[\s\.\-]?[0-9]){8}\b'
)

# Địa chỉ cơ sở, phòng học thêm, nhà riêng
FACILITY_ADDRESS_REGEX = re.compile(
    r'(?i)(?:địa chỉ|cơ sở\s*\d*|trụ sở|đ\/c|phòng học|lớp học thêm)[\s:]*(?:số\s*\d+|tầng\s*\d+|ngõ\s*\d+|ngách\s*\d+|đường\s+[^,\n]+|quận\s+[^,\n]+|huyện\s+[^,\n]+|[^\n,]{5,50}(?:hà nội|tp\.?\s*hcm|hồ chí minh|đà nẵng|hải phòng|vĩnh phúc|nam định|nghệ an|thanh hóa|cần thơ))',
    re.IGNORECASE
)

# Email cá nhân trôi nổi rao bán tài liệu
PERSONAL_EMAIL_REGEX = re.compile(
    r'\b[a-zA-Z0-9._%+-]+@(gmail|yahoo|hotmail|outlook)\.com\b',
    re.IGNORECASE
)

# Link mạng xã hội & Website bên thứ ba
SOCIAL_AND_WEB_REGEX = re.compile(
    r'(?i)\b(?:https?:\/\/)?(?:www\.)?(?:facebook\.com|fb\.com|zalo\.me|t\.me|tiktok\.com|youtube\.com|thuvienhoclieu\.org|tailieumontoan\.com|toanmath\.com|dethithuvn\.com|violet\.vn)\/[^\s,;]+',
    re.IGNORECASE
)

# Tên miền website nguồn trôi nổi trên header/footer
SOURCE_DOMAIN_NAMES_REGEX = re.compile(
    r'(?i)\b(?:thuvienhoclieu\.(?:com|vn|org)|tailieumontoan\.(?:com|vn)|toanmath\.com|dethithuvn\.com|onthidgnl\.com|hocmai\.vn)\b',
    re.IGNORECASE
)

# Giá bán, STK ngân hàng, VIP có phí
VIP_PRICE_REGEX = re.compile(
    r'(?i)(?:giá\s*:\s*\d+[\s\.]?[kKđĐ]|chuyển khoản\s*(?:stk|số tài khoản|vào tk)|ngân hàng\s+(?:vietcombank|mbbank|bidv|agribank|techcombank|acb|vpbank)|tài liệu\s*vip\s*có\s*phí|mua trọn bộ\s*\d+k)',
    re.IGNORECASE
)

# Watermark chữ mờ chéo trang phổ biến
WATERMARK_TEXT_REGEX = re.compile(
    r'(?i)(?:website\s*:\s*[a-z0-9\.\-_]+\.(?:com|vn|org)|đề thi thầy\s+[^\n]+|sưu tầm và biên soạn\s*:\s*thầy|tài liệu nội bộ\s*-\s*cấm sao chép|bản quyền thuộc về\s+[^\n]+)',
    re.IGNORECASE
)

# ==============================================================================
# 2. BOUNDARY PRINCIPLE WHITELIST (BẢO LƯU 100% NGUỒN GỐC HỌC THUẬT E-E-A-T)
# ==============================================================================
WHITELIST_PRESERVE_PATTERNS = [
    re.compile(r'(?i)\b(?:thcs|thpt|tiểu học|trường thcs|trường thpt|trường chuyên|đại học|sở gd&đt|sở giáo dục|phòng gd&đt|bộ gd&đt)\b'),
    re.compile(r'(?i)\b(?:chu văn an|amsterdam|cầu giấy|chuyên sư phạm|lương thế vinh|chuyên ngoại ngữ|lê hồng phong|trần phú|chuyên bến tre)\b'),
    re.compile(r'(?i)\b(?:đề thi|kỳ thi|học kỳ|giữa kỳ|cuối kỳ|hsg|olympic|tuyển sinh|vào 10|thptqg|đgnl|hsa|tsa)\b'),
]

class DeepSanitizerEngine:
    """Engine khử trùng, làm sạch triệt để Watermark, PII, SĐT, Email và thông tin rác bên thứ ba.
    Tuân thủ nghiêm ngặt tiêu chuẩn BEEKIP-DOC-STD-2026 Mục 3.3.
    """

    def __init__(self):
        self.stats = {
            "watermarks_found": 0,
            "phones_found": 0,
            "facilities_found": 0,
            "emails_found": 0,
            "social_links_found": 0,
            "vip_prices_found": 0,
            "preserved_entities": 0,
        }

    def is_preserved_academic_entity(self, text: str) -> bool:
        """Kiểm tra xem chuỗi có thuộc danh mục Bảo lưu nguồn gốc học thuật (Trường, Sở GD&ĐT) hay không."""
        for pattern in WHITELIST_PRESERVE_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def scan_text_anomalies(self, text: str) -> List[Dict[str, Any]]:
        """Quét và phân tích toàn diện các yếu tố rác / PII trong chuỗi văn bản."""
        findings: List[Dict[str, Any]] = []

        # 1. Quét SĐT có tiền tố
        for match in PHONE_PREFIXED_REGEX.finditer(text):
            val = match.group(0).strip()
            findings.append({"type": "PHONE_PREFIXED", "value": val, "span": match.span()})

        # 2. Quét SĐT độc lập
        for match in PHONE_STANDALONE_REGEX.finditer(text):
            val = match.group(0).strip()
            # Tránh nhầm lẫn với số năm học ví dụ 2024-2025
            if not re.search(r'202[0-9]', val):
                findings.append({"type": "PHONE_STANDALONE", "value": val, "span": match.span()})

        # 3. Quét địa chỉ cơ sở
        for match in FACILITY_ADDRESS_REGEX.finditer(text):
            val = match.group(0).strip()
            if not self.is_preserved_academic_entity(val):
                findings.append({"type": "FACILITY_ADDRESS", "value": val, "span": match.span()})
            else:
                self.stats["preserved_entities"] += 1

        # 4. Quét email cá nhân
        for match in PERSONAL_EMAIL_REGEX.finditer(text):
            val = match.group(0).strip()
            findings.append({"type": "PERSONAL_EMAIL", "value": val, "span": match.span()})

        # 5. Quét link mạng xã hội & domain bên thứ ba
        for match in SOCIAL_AND_WEB_REGEX.finditer(text):
            val = match.group(0).strip()
            findings.append({"type": "SOCIAL_WEB_LINK", "value": val, "span": match.span()})

        for match in SOURCE_DOMAIN_NAMES_REGEX.finditer(text):
            val = match.group(0).strip()
            findings.append({"type": "SOURCE_DOMAIN", "value": val, "span": match.span()})

        # 6. Quét giá bán VIP
        for match in VIP_PRICE_REGEX.finditer(text):
            val = match.group(0).strip()
            findings.append({"type": "VIP_PRICE", "value": val, "span": match.span()})

        # 7. Quét watermark dạng text
        for match in WATERMARK_TEXT_REGEX.finditer(text):
            val = match.group(0).strip()
            if not self.is_preserved_academic_entity(val):
                findings.append({"type": "WATERMARK_TEXT", "value": val, "span": match.span()})
            else:
                self.stats["preserved_entities"] += 1

        return findings

    def clean_text_content(self, text: str) -> Tuple[str, int]:
        """Làm sạch chuỗi text thuần, xóa sạch PII và thay thế an toàn không làm hỏng công thức Toán."""
        cleaned = text
        redactions_count = 0

        # Thứ tự thay thế từ cụ thể đến chung
        patterns = [
            (PHONE_PREFIXED_REGEX, "[ĐÃ KHỬ PII - SĐT]"),
            (PERSONAL_EMAIL_REGEX, "[ĐÃ KHỬ PII - EMAIL]"),
            (VIP_PRICE_REGEX, "[100% MIỄN PHÍ CỘNG ĐỒNG]"),
            (SOURCE_DOMAIN_NAMES_REGEX, "tailieu.beekip.vn"),
            (SOCIAL_AND_WEB_REGEX, "https://tailieu.beekip.vn"),
            (WATERMARK_TEXT_REGEX, ""),
        ]

        for regex, replacement in patterns:
            cleaned, count = regex.subn(replacement, cleaned)
            redactions_count += count

        return cleaned, redactions_count

    def audit_pdf_cleanliness(self, pdf_path: Path) -> Dict[str, Any]:
        """Kiểm toán độ sạch của file PDF theo Tiêu chuẩn Mục 3.3 mà không sửa đổi file."""
        if not pdf_path.exists():
            return {"success": False, "error": f"File không tồn tại: {pdf_path}"}

        findings_by_page: Dict[int, List[Dict[str, Any]]] = {}
        total_findings = 0
        watermark_images_detected = 0

        try:
            doc = pymupdf.open(str(pdf_path))
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")

                # Scan text anomalies
                page_findings = self.scan_text_anomalies(text)
                if page_findings:
                    findings_by_page[page_num + 1] = page_findings
                    total_findings += len(page_findings)

                # Scan translucent background image watermarks (XObjects)
                # Chỉ coi là watermark nếu ảnh chiếm phần lớn diện tích trang (background overlay >= 60%)
                # Hình học, đồ thị bài toán toán học chiếm diện tích cục bộ bên trong câu hỏi, không phải watermark
                for img_info in page.get_images(full=True):
                    xref = img_info[0]
                    rects = page.get_image_rects(xref)
                    if rects:
                        page_area = max(1.0, page.rect.width * page.rect.height)
                        for r in rects:
                            img_area = r.width * r.height
                            if (img_area / page_area) >= 0.60:
                                watermark_images_detected += 1
                    else:
                        base_img = doc.extract_image(xref)
                        if base_img:
                            w, h = base_img.get("width", 0), base_img.get("height", 0)
                            if w >= 1500 and h >= 2000:
                                watermark_images_detected += 1

            doc.close()

            is_clean = (total_findings == 0 and watermark_images_detected == 0)
            return {
                "success": True,
                "file_path": str(pdf_path),
                "is_clean": is_clean,
                "total_findings": total_findings,
                "watermark_images_detected": watermark_images_detected,
                "findings_by_page": findings_by_page,
            }
        except Exception as e:
            logger.error("Lỗi khi kiểm toán PDF %s: %s", pdf_path, e)
            return {"success": False, "error": str(e)}

    def sanitize_pdf_derivative(self, input_pdf: Path, output_pdf: Path) -> Dict[str, Any]:
        """Tạo tệp phái sinh PDF đã làm sạch triệt để Watermark, PII, SĐT, Email theo Mục 3.3."""
        if not input_pdf.exists():
            return {"success": False, "error": f"Tệp đầu vào không tồn tại: {input_pdf}"}

        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        redactions_applied = 0

        try:
            doc = pymupdf.open(str(input_pdf))

            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Quét các khối văn bản để tìm tọa độ cần bóc tách (Redaction) trên toàn bộ 7 nhóm PII/watermark
                text_instances = []
                for finding in self.scan_text_anomalies(page.get_text()):
                    matched_text = str(finding.get("value") or "").strip()
                    if matched_text and len(matched_text) >= 4 and not self.is_preserved_academic_entity(matched_text):
                        rects = page.search_for(matched_text)
                        for rect in rects:
                            text_instances.append(rect)

                # Áp dụng Redaction Annotation (xóa sạch vùng text vi phạm, phủ nền trắng hoàn toàn)
                for rect in text_instances:
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    redactions_applied += 1

                if text_instances:
                    page.apply_redactions()

            # Lưu tệp phái sinh tối ưu hóa (garbage=4 loại bỏ toàn bộ đối tượng mồ côi)
            doc.save(str(output_pdf), garbage=4, deflate=True, no_new_id=True)
            doc.close()

            return {
                "success": True,
                "input_file": str(input_pdf),
                "output_file": str(output_pdf),
                "redactions_applied": redactions_applied,
                "file_size_bytes": output_pdf.stat().st_size
            }
        except Exception as e:
            logger.error("Lỗi khi sanitize PDF phái sinh %s: %s", input_pdf, e)
            return {"success": False, "error": str(e)}

    def audit_docx_cleanliness(self, docx_path: Path) -> Dict[str, Any]:
        """Kiểm toán độ sạch của file DOCX (quét OOXML header/footer/shapes) theo Mục 3.3."""
        if not docx_path.exists():
            return {"success": False, "error": f"File không tồn tại: {docx_path}"}

        watermark_shapes = 0
        pii_matches = 0

        try:
            with zipfile.ZipFile(docx_path, 'r') as zf:
                for filename in zf.namelist():
                    if filename.startswith('word/header') or filename.startswith('word/footer') or filename == 'word/document.xml':
                        xml_content = zf.read(filename).decode('utf-8', errors='ignore')

                        # Kiểm tra WordArt / PowerPlusWatermark
                        if 'type="#_x0000_t136"' in xml_content or 'PowerPlusWatermark' in xml_content or 'WordArt' in xml_content:
                            watermark_shapes += 1

                        # Kiểm tra PII text trong XML
                        anomalies = self.scan_text_anomalies(xml_content)
                        pii_matches += len(anomalies)

            return {
                "success": True,
                "file_path": str(docx_path),
                "is_clean": (watermark_shapes == 0 and pii_matches == 0),
                "watermark_shapes": watermark_shapes,
                "pii_matches": pii_matches
            }
        except Exception as e:
            logger.error("Lỗi khi kiểm toán DOCX %s: %s", docx_path, e)
            return {"success": False, "error": str(e)}

    def audit_pptx_cleanliness(self, pptx_path: Path) -> Dict[str, Any]:
        """Kiểm toán độ sạch của file PowerPoint PPTX (quét OOXML slides/masters/shapes) theo Mục 3.3."""
        if not pptx_path.exists():
            return {"success": False, "error": f"File không tồn tại: {pptx_path}"}

        watermark_shapes = 0
        pii_matches = 0

        try:
            with zipfile.ZipFile(pptx_path, 'r') as zf:
                for filename in zf.namelist():
                    if filename.startswith('ppt/slides/') or filename.startswith('ppt/slideMasters/') or filename.startswith('ppt/notesSlides/'):
                        xml_content = zf.read(filename).decode('utf-8', errors='ignore')

                        if 'type="#_x0000_t136"' in xml_content or 'PowerPlusWatermark' in xml_content or 'WordArt' in xml_content:
                            watermark_shapes += 1

                        anomalies = self.scan_text_anomalies(xml_content)
                        pii_matches += len(anomalies)

            return {
                "success": True,
                "file_path": str(pptx_path),
                "is_clean": (watermark_shapes == 0 and pii_matches == 0),
                "watermark_shapes": watermark_shapes,
                "pii_matches": pii_matches
            }
        except Exception as e:
            logger.error("Lỗi khi kiểm toán PPTX %s: %s", pptx_path, e)
            return {"success": False, "error": str(e)}
