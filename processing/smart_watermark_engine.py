import io
import logging
import re
from pathlib import Path
from typing import List, Optional, Union
import pymupdf

logger = logging.getLogger("beekip.watermark")

DE_WATERMARK_PATTERNS = [
    re.compile(r'(?i)(?:https?://)?(?:www\.)?(?:toanmath|thuvienvatly|tailieudieuky|tailieuonthi|thuvienhoclieu|vietjack|vndoc|loigiaihay|tech12h)\.(?:com|vn|net|edu\.vn|org)'),
    re.compile(r'(?i)(?:hotline|zalo|liên hệ|fanpage|sđt|đt)\s*[:.]?\s*(?:09\d|08\d|07\d|03\d)[\d.\s]{7,10}'),
    re.compile(r'(?i)nhóm\s+(?:vip|zalo|chia sẻ tài liệu|hỗ trợ giáo viên)'),
    re.compile(r'(?i)sưu\s+tầm\s+và\s+biên\s+soạn'),
]

DOMAIN_KEYWORDS = [
    "toanmath.com", "thuvienvatly.com", "tailieudieuky.com",
    "tailieuonthi.edu.vn", "thuvienhoclieu.com", "vietjack.com",
    "vndoc.com", "loigiaihay.com", "tech12h.com"
]

BEEKIP_WATERMARK_TEXT = "tailieu.beekip.vn - Học liệu mở K12"
BEEKIP_FOOTER_TEXT = "🌐 Kho học liệu mở K-12 miễn phí | tailieu.beekip.vn"

# Colors: Light Slate Gray (#CBD5E1) and Slate (#64748B)
WATERMARK_COLOR = (203 / 255.0, 213 / 255.0, 225 / 255.0)
FOOTER_COLOR = (100 / 255.0, 116 / 255.0, 139 / 255.0)

class SmartWatermarkEngine:
    """
    Cleans unwanted noisy annotations/domains and applies subtle Beekip underlay branding.
    Maintains 100% legibility of learning text, equations, and diagrams.
    """

    @classmethod
    def clean_and_brand_pdf(
        cls,
        pdf_input: Union[bytes, str, Path],
        output_path: Optional[Union[str, Path]] = None,
        apply_cleanup: bool = True,
        apply_beekip_branding: bool = True
    ) -> bytes:
        """
        Process PDF entirely in RAM or write to output_path.
        Returns the processed PDF bytes.
        """
        if isinstance(pdf_input, (str, Path)):
            doc = pymupdf.open(str(pdf_input))
        else:
            doc = pymupdf.open(stream=pdf_input, filetype="pdf")

        for page in doc:
            rect = page.rect
            width = rect.width
            height = rect.height

            # Phase 1: Clean legacy annotations and noise text
            if apply_cleanup:
                cls._clean_page_noise(page, width, height)

            # Phase 2: Add subtle Beekip watermark & footer
            if apply_beekip_branding:
                cls._add_beekip_branding(page, width, height)

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(out_file), garbage=3, deflate=True)
            doc.close()
            return out_file.read_bytes()

        output_bytes = doc.tobytes(garbage=3, deflate=True)
        doc.close()
        return output_bytes

    @classmethod
    def _clean_page_noise(cls, page: pymupdf.Page, width: float, height: float) -> None:
        """Scan page text blocks for legacy advertising, domains, and hotlines."""
        has_redactions = False

        # 1. Unlink watermark annotations if present
        for annot in list(page.annots()):
            try:
                info = annot.info
                if info and info.get("subject", "").lower() == "watermark":
                    page.delete_annot(annot)
            except Exception:
                pass

        # 2. Extract text blocks and apply pattern redaction
        blocks = page.get_text("blocks")
        for b in blocks:
            b_x0, b_y0, b_x1, b_y1, b_text, *_ = b
            b_rect = pymupdf.Rect(b_x0, b_y0, b_x1, b_y1)

            # Check marginal scrubbing (headers & footers)
            is_top_margin = b_y0 < 28
            is_bottom_margin = b_y1 > (height - 28)

            if (is_top_margin or is_bottom_margin) and any(d in b_text.lower() for d in DOMAIN_KEYWORDS):
                page.add_redact_annot(b_rect, fill=(1, 1, 1))
                has_redactions = True
                continue

            # Check general text patterns
            for pattern in DE_WATERMARK_PATTERNS:
                if pattern.search(b_text):
                    page.add_redact_annot(b_rect, fill=(1, 1, 1))
                    has_redactions = True
                    break

        if has_redactions:
            try:
                page.apply_redactions()
            except Exception as e:
                logger.debug("Failed applying redactions on page %s: %s", page.number, e)

    @classmethod
    def _add_beekip_branding(cls, page: pymupdf.Page, width: float, height: float) -> None:
        """Insert subtle underlay watermark and footer attribution."""
        cx = width / 2.0
        cy = height / 2.0

        # Center Underlay Watermark: 35 degrees, 7% opacity, Light Slate Gray
        fontsize = 32.0
        text_len = pymupdf.get_text_length(BEEKIP_WATERMARK_TEXT, fontsize=fontsize)
        start_point = pymupdf.Point(cx - text_len / 2.0, cy)

        # Matrix for 35-degree diagonal rotation (counter-clockwise upward)
        morph_center = pymupdf.Point(cx, cy)
        rot_matrix = pymupdf.Matrix(-35)

        try:
            page.insert_text(
                start_point,
                BEEKIP_WATERMARK_TEXT,
                fontsize=fontsize,
                color=WATERMARK_COLOR,
                morph=(morph_center, rot_matrix),
                overlay=False,  # Underlay layer
                fill_opacity=0.07  # 7% subtle opacity
            )
        except Exception as e:
            logger.debug("Failed to insert center watermark on page %s: %s", page.number, e)

        # Running Footer Bar at bottom
        footer_point = pymupdf.Point(36, height - 12)
        try:
            page.insert_text(
                footer_point,
                BEEKIP_FOOTER_TEXT,
                fontsize=7.5,
                color=FOOTER_COLOR,
                overlay=True
            )
        except Exception as e:
            logger.debug("Failed to insert footer bar on page %s: %s", page.number, e)
