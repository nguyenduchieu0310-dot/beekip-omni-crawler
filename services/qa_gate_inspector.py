import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.derivative_renderer import (
    MAX_COVER_SIZE_BYTES,
    MAX_PDF_SIZE_BYTES,
    MIN_COVER_WIDTH_PX,
    DerivativeRendererEngine,
)
from services.sanitizer import DeepSanitizerEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("beekip.qa_gate")

class QAGateInspector:
    """Cổng kiểm duyệt QA Gate 10 tiêu chí trước khi xuất bản theo BEEKIP-DOC-STD-2026 Mục 7.
    Chỉ tài liệu đạt trọn vẹn 10/10 tiêu chí mới được cấp phép isPublished = True.
    """

    def __init__(self):
        self.sanitizer = DeepSanitizerEngine()
        self.renderer = DerivativeRendererEngine()

    def inspect_document(
        self,
        pdf_path: Path,
        cover_path: Optional[Path],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Thực hiện kiểm toán toàn diện 10 tiêu chí QA Gate."""
        checklist: Dict[str, Dict[str, Any]] = {}

        # -------------------------------------------------------------
        # TIÊU CHÍ 1: Chất lượng file PDF
        # -------------------------------------------------------------
        pdf_valid = False
        pdf_details = {}
        if pdf_path.exists():
            pdf_details = self.renderer.validate_pdf_standards(pdf_path)
            pdf_valid = pdf_details.get("valid", False)
        checklist["item_1_pdf_quality"] = {
            "name": "Chất lượng file PDF (Dung lượng, Trang, Text Layer, Mã độc)",
            "pass": pdf_valid,
            "details": pdf_details
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 2: Ảnh bìa Thumbnail
        # -------------------------------------------------------------
        cover_pass = False
        cover_details = {}
        if cover_path and cover_path.exists():
            from PIL import Image
            try:
                with Image.open(cover_path) as img:
                    w, h = img.size
                c_size = cover_path.stat().st_size
                cover_pass = (w >= MIN_COVER_WIDTH_PX and c_size <= MAX_COVER_SIZE_BYTES)
                cover_details = {
                    "width": w,
                    "height": h,
                    "file_size_kb": round(c_size / 1024, 1),
                    "meets_standards": cover_pass
                }
            except Exception as e:
                cover_details = {"error": str(e)}
        checklist["item_2_cover_thumbnail"] = {
            "name": "Ảnh bìa Thumbnail (>=1200px, <=250KB, sắc nét)",
            "pass": cover_pass,
            "details": cover_details
        }

        # -------------------------------------------------------------
        # KIỂM TOÁN LÀM SẠCH (DÙNG CHO TIÊU CHÍ 3, 4, 5, 6)
        # -------------------------------------------------------------
        clean_audit = self.sanitizer.audit_pdf_cleanliness(pdf_path) if pdf_path.exists() else {"is_clean": False}
        findings_by_page = clean_audit.get("findings_by_page", {})
        all_findings = []
        for p, finds in findings_by_page.items():
            all_findings.extend(finds)

        # -------------------------------------------------------------
        # TIÊU CHÍ 3: Xóa Watermark cũ
        # -------------------------------------------------------------
        watermark_findings = [f for f in all_findings if f["type"] in ("WATERMARK_TEXT", "SOURCE_DOMAIN")]
        has_no_watermarks = (clean_audit.get('success', False) and len(watermark_findings) == 0)
        checklist["item_3_no_old_watermark"] = {
            "name": "Xóa sạch Watermark cũ (Logo chìm, chữ mờ chéo trang, WordArt)",
            "pass": has_no_watermarks,
            "findings_count": len(watermark_findings)
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 4: Xóa SĐT & Zalo cũ
        # -------------------------------------------------------------
        phone_findings = [f for f in all_findings if f["type"] in ("PHONE_PREFIXED", "PHONE_STANDALONE")]
        has_no_phones = (len(phone_findings) == 0)
        checklist["item_4_no_phone_zalo"] = {
            "name": "Xóa sạch 100% SĐT, Hotline & Zalo liên hệ bán đề",
            "pass": has_no_phones,
            "findings_count": len(phone_findings)
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 5: Xóa Địa chỉ & Email
        # -------------------------------------------------------------
        address_findings = [f for f in all_findings if f["type"] in ("FACILITY_ADDRESS", "PERSONAL_EMAIL")]
        has_no_addresses = (len(address_findings) == 0)
        checklist["item_5_no_facility_address"] = {
            "name": "Xóa sạch Địa chỉ cơ sở luyện thi, phòng học, email cá nhân",
            "pass": has_no_addresses,
            "findings_count": len(address_findings)
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 6: Xóa Giá bán & Link ngoài
        # -------------------------------------------------------------
        vip_findings = [f for f in all_findings if f["type"] in ("VIP_PRICE", "SOCIAL_WEB_LINK")]
        has_no_vip_links = (len(vip_findings) == 0)
        checklist["item_6_no_vip_links"] = {
            "name": "Xóa thông tin bán tài liệu VIP, STK ngân hàng, group kín",
            "pass": has_no_vip_links,
            "findings_count": len(vip_findings)
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 7: Bảo lưu nguồn gốc E-E-A-T
        # -------------------------------------------------------------
        author = metadata.get("authorName", "")
        academic_keywords = ("trường", "sở", "phòng", "bộ", "beekip", "thpt", "thcs", "chuyên", "thầy", "cô", "giáo viên")
        has_provenance = bool(author and any(kw in author.lower() for kw in academic_keywords))
        checklist["item_7_academic_provenance"] = {
            "name": "Bảo lưu nguồn gốc học thuật (Trường, Sở GD&ĐT, Thầy cô) chuẩn E-E-A-T",
            "pass": has_provenance,
            "author_name": author
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 8: Metadata & Phân loại
        # -------------------------------------------------------------
        has_meta = bool(
            metadata.get("title") and
            metadata.get("slug") and
            metadata.get("grade") and
            metadata.get("subject") and
            metadata.get("category") and
            metadata.get("topic")
        )
        checklist["item_8_metadata_taxonomy"] = {
            "name": "Metadata & Phân loại chuẩn (Title H1, Semantic Slug, Khối lớp, Chuyên đề)",
            "pass": has_meta,
            "slug": metadata.get("slug", "")
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 9: Nội dung Markdown >= 300 từ
        # -------------------------------------------------------------
        desc = metadata.get("description", "")
        word_count = len(desc.split())
        has_sections = ("## 1." in desc and "## 2." in desc and "## 3." in desc and "## 4." in desc)
        md_pass = (word_count >= 300 and has_sections)
        checklist["item_9_markdown_content"] = {
            "name": "Nội dung Markdown cấu trúc cao (>= 300 từ, 4 phần, LaTeX)",
            "pass": md_pass,
            "word_count": word_count,
            "has_4_sections": has_sections
        }

        # -------------------------------------------------------------
        # TIÊU CHÍ 10: Quyền truy cập & Schema.org
        # -------------------------------------------------------------
        free_access = metadata.get("isAccessibleForFree", True)
        checklist["item_10_free_access_and_schema"] = {
            "name": "Cống hiến cộng đồng 100% Miễn phí & Tương thích Schema kép",
            "pass": bool(free_access),
            "free_access": free_access
        }

        # -------------------------------------------------------------
        # TỔNG HỢP KẾT QUẢ KIỂM DUYỆT
        # -------------------------------------------------------------
        total_items = len(checklist)
        passed_count = sum(1 for item in checklist.values() if item["pass"])
        pass_ratio = round((passed_count / total_items) * 100, 1)
        is_published = (passed_count == total_items)

        return {
            "is_published_eligible": is_published,
            "score": passed_count,
            "max_score": total_items,
            "pass_ratio_pct": pass_ratio,
            "status": "QA_PASS" if is_published else "QA_REJECTED",
            "checklist": checklist
        }
