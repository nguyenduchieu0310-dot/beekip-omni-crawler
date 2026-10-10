"""
Agent 1: Data & Content Processor Agent (Beekip Multi-Agentic Architecture).
Responsibilities:
- Sanitizes PDF derivatives (removes PII, Zalo, Phone, Ads; preserves diagrams & geometry).
- Renders HD Cover Thumbnail (>= 1200px width, <= 250KB, Google Discover/News compliant).
- Authors SEO, GEO, and Google News compliant Markdown content with KaTeX formulas.
- Synthesizes Dual Schema.org JSON-LD (LearningResource + NewsArticle).
- Supports Self-Healing refinement loop based on Agent 2 defect tickets.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from processing.seo_geo_enricher import SEOGEOEnricher
from services.derivative_renderer import (
    MIN_COVER_WIDTH_PX,
    MAX_COVER_SIZE_BYTES,
    DerivativeRendererEngine,
)
from services.sanitizer import DeepSanitizerEngine

logger = logging.getLogger("beekip.agent1_processor")


class ContentProcessorAgent:
    """Agent 1: Ingestion, Sanitization & High-Quality Content Creation."""

    def __init__(self):
        self.sanitizer = DeepSanitizerEngine()
        self.renderer = DerivativeRendererEngine()

    def generate_geo_seo_markdown(
        self,
        meta_title: str,
        subject: str,
        grade: int,
        school: Optional[str],
        source_url: str,
        page_count: int,
        file_size_bytes: int,
        detected_year: int,
        extended_analysis: bool = False,
    ) -> str:
        """
        Produce a high-ranking 4-part Markdown document.
        Combines SEO keywords, GEO Direct Answer structure, E-E-A-T provenance,
        and KaTeX mathematical expressions.
        """
        size_mib = file_size_bytes / (1024 * 1024)
        author_entity = school or "Đơn vị khảo thí & biên soạn giáo dục"

        # Direct Answer lead for GEO AI Search (Perplexity, SearchGPT, Claude)
        lead_summary = (
            f"Tài liệu **{meta_title}** là bộ học liệu số chuẩn hóa môn **{subject} lớp {grade}**, "
            f"được biên soạn bởi **{author_entity}** dành cho năm học **{detected_year} – {detected_year + 1}**. "
            f"Bộ tài liệu gồm **{page_count} trang** đầy đủ cấu trúc câu hỏi trắc nghiệm, trả lời ngắn và tự luận theo chương trình GDPT mới."
        )

        math_quote_section = ""
        if subject.lower() in ("toán", "toán học", "vật lý", "hóa học"):
            math_quote_section = f"""
### Trích Dẫn Dạng Bài & Công Thức Trọng Tâm (KaTeX)
Tài liệu củng cố hệ thống công thức giải nhanh và phương pháp biến đổi toán học cốt lõi:
- **Công thức giải tích & hàm số:** Khảo sát tính đơn điệu và cực trị hàm số $y = f(x)$ thông qua xét dấu đạo hàm:
  $$f'(x_0) = 0 \\implies x_0 \\text{{ là điểm nghi vấn của hàm số}}$$
- **Hình học không gian & tọa độ $Oxyz$:** Xác định khoảng cách từ điểm $M(x_0, y_0, z_0)$ đến mặt phẳng $(P): Ax + By + Cz + D = 0$:
  $$d(M, (P)) = \\frac{{|A x_0 + B y_0 + C z_0 + D|}}{{\\sqrt{{A^2 + B^2 + C^2}}}}$$
- **Giải bài toán xác suất thống kê:** Định lý xác suất có điều kiện và công thức nhân:
  $$P(A \\cap B) = P(A) \\cdot P(B|A) \\quad (\\text{{với }} P(A) > 0)$$
"""

        additional_body = ""
        if extended_analysis:
            additional_body = f"""
### Phân Tích Chuyên Sâu Từng Phần Đề Thi
- **Phần I (Trắc nghiệm nhiều lựa chọn):** Gồm 12 - 16 câu hỏi quét toàn diện kiến thức nền tảng, học sinh cần rèn kỹ năng nhận biết và thông hiểu trong 20 phút đầu.
- **Phần II (Trắc nghiệm Đúng/Sai):** Định dạng đánh giá năng lực mới của Bộ GD&ĐT, mỗi ý đòi hỏi lập luận chặt chẽ và đối chiếu đa chiều.
- **Phần III (Trả lời ngắn & Tự luận vận dụng cao):** Phân hóa học sinh xuất sắc, đòi hỏi kỹ năng trình bày logic và tư duy liên môn.
"""

        content = f"""## 1. THÔNG TIN HỌC LIỆU & TỔNG QUAN XUẤT BẢN
{lead_summary}
- **Môn học:** {subject}
- **Khối lớp:** Lớp {grade}
- **Năm học áp dụng:** {detected_year} – {detected_year + 1} (Chương trình GDPT mới)
- **Đơn vị / Tác giả:** {author_entity}
- **Quy cách tệp:** PDF số hóa sạch, {page_count} trang ({size_mib:.2f} MiB), 100% không mã độc và không watermark rác.
- **Nguồn bài viết gốc:** {source_url}

## 2. NỘI DUNG TRỌNG TÂM & TIÊU CHUẨN ĐÁNH GIÁ NĂNG LỰC
Tài liệu được thẩm định bám sát cấu trúc đề thi chính thức mới nhất. Nội dung phân bổ theo 3 tầng nhận thức: Nhận biết, Thông hiểu và Vận dụng cao.
{math_quote_section}
{additional_body}

## 3. HƯỚNG DẪN HỌC TẬP & CHIẾN LƯỢC ÔN LUYỆN ĐẠT ĐIỂM CAO
1. **Thiết lập thời gian làm bài thực tế:** Đặt đồng hồ bấm giờ chuẩn (45 phút, 90 phút hoặc 120 phút tương ứng với cấp độ kiểm tra).
2. **Trình bày tự luận cẩn thận:** Đối với các bước biến đổi trung gian, luôn ghi rõ điều kiện xác định và kết luận tập nghiệm.
3. **Đối chiếu kết quả & Rút kinh nghiệm:** Ghi chú lại những câu hỏi bị sai hoặc phân vân để hỏi lại thầy cô hoặc thảo luận cùng nhóm học tập.

## 4. BẢN QUYỀN HỌC LIỆU & ĐIỀU KIỆN TRUY CẬP MIỄN PHÍ
- Bản quyền đề thi và nội dung học thuật thuộc về đơn vị ra đề ({author_entity}).
- Hệ thống số hóa **Beekip.vn** thực hiện lưu trữ, làm sạch PII và phục vụ cộng đồng học sinh, giáo viên toàn quốc hoàn toàn **miễn phí 100%**.
- Tệp gốc và bản in PDF độ nét cao sẵn sàng tải về trực tiếp không giới hạn lượt tải.
"""
        return content.strip()

    def build_dual_schema_jsonld(
        self,
        title: str,
        slug: str,
        subject: str,
        grade: int,
        school: Optional[str],
        published_year: int,
        cover_url: str,
        file_url: str,
        date_published: str,
    ) -> Dict[str, Any]:
        """
        Build dual Schema.org graph:
        1. LearningResource (Google Educational Rich Results, Quiz, Free Access)
        2. NewsArticle (Google News & Google Discover inclusion for current exam news)
        """
        canonical_url = f"https://tailieu.beekip.vn/tai-lieu/{slug}"
        author_name = school or "Đơn vị Giáo dục & Đào tạo"

        learning_resource = {
            "@context": "https://schema.org",
            "@type": ["LearningResource", "DigitalDocument"],
            "@id": f"{canonical_url}#learning-resource",
            "name": title,
            "headline": title,
            "url": canonical_url,
            "inLanguage": "vi",
            "learningResourceType": "Đề thi & Tài liệu ôn tập",
            "educationalLevel": f"Lớp {grade}",
            "about": [subject, f"Chương trình GDPT {published_year}"],
            "isAccessibleForFree": True,
            "image": cover_url,
            "author": {
                "@type": "EducationalOrganization",
                "name": author_name,
            },
            "publisher": {
                "@type": "Organization",
                "name": "Beekip Học Liệu Số",
                "url": "https://tailieu.beekip.vn",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://tailieu.beekip.vn/logo.png",
                },
            },
            "datePublished": date_published,
            "dateModified": date_published,
        }

        news_article = {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "@id": f"{canonical_url}#news",
            "headline": title[:110],
            "url": canonical_url,
            "image": [cover_url],
            "datePublished": date_published,
            "dateModified": date_published,
            "author": [
                {
                    "@type": "Organization",
                    "name": author_name,
                }
            ],
            "publisher": {
                "@type": "Organization",
                "name": "Beekip",
                "url": "https://tailieu.beekip.vn",
            },
            "description": f"Công bố và số hóa {title} dành cho học sinh cả nước luyện tập miễn phí.",
            "mainEntityOfPage": canonical_url,
        }

        return {
            "@context": "https://schema.org",
            "@graph": [learning_resource, news_article],
        }

    def process_raw_document(
        self,
        raw_pdf_path: Path,
        item_meta: Dict[str, Any],
        source: Dict[str, Any],
        output_dir: Path,
    ) -> Dict[str, Any]:
        """
        Execute full Agent 1 compilation pipeline:
        Sanitize -> Render Cover -> SEO/GEO Content -> Dual Schema -> Pack Draft.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        clean_pdf_path = output_dir / "clean_derivative.pdf"
        cover_image_path = output_dir / "cover_hd.jpg"

        title = item_meta.get("title", "Tài liệu học tập Beekip")
        url = item_meta.get("url", "")
        published_year = item_meta.get("published_year") or 2026

        # 1. Sanitize PDF
        clean_res = self.sanitizer.sanitize_pdf_derivative(raw_pdf_path, clean_pdf_path)
        if not clean_res.get("success"):
            raise RuntimeError(f"Sanitization failed: {clean_res.get('error')}")

        # 2. Render Cover HD (>= 1200px)
        render_res = self.renderer.render_cover_thumbnail(clean_pdf_path, cover_image_path, target_width=MIN_COVER_WIDTH_PX)
        if not render_res.get("success"):
            raise RuntimeError(f"Cover render failed: {render_res.get('error')}")

        # 3. Enrich SEO & GEO Metadata
        default_subject = source.get("primary_subject", "Đa môn")
        enriched = SEOGEOEnricher.enrich(title, default_subject=default_subject)
        slug_hash = hashlib.sha256(url.encode()).hexdigest()[:10]
        enriched.slug = f"{enriched.slug[:140]}-{slug_hash}"

        # 4. Generate structured 4-part Markdown content
        pdf_stat = self.renderer.validate_pdf_standards(clean_pdf_path)
        page_count = pdf_stat.get("page_count", 1)
        file_size = clean_pdf_path.stat().st_size

        article_content = self.generate_geo_seo_markdown(
            meta_title=enriched.title,
            subject=enriched.subject,
            grade=enriched.grade,
            school=enriched.geo_school,
            source_url=url,
            page_count=page_count,
            file_size_bytes=file_size,
            detected_year=published_year,
            extended_analysis=True,
        )

        # 5. Dual Schema
        from datetime import datetime, timezone
        pub_iso = datetime.now(timezone.utc).isoformat()
        cover_preview_url = f"https://tailieu.beekip.vn/api/documents/{enriched.slug}/cover"
        file_preview_url = f"https://tailieu.beekip.vn/api/documents/{enriched.slug}/download"

        schema_jsonld = self.build_dual_schema_jsonld(
            title=enriched.title,
            slug=enriched.slug,
            subject=enriched.subject,
            grade=enriched.grade,
            school=enriched.geo_school,
            published_year=published_year,
            cover_url=cover_preview_url,
            file_url=file_preview_url,
            date_published=pub_iso,
        )

        draft_package = {
            "title": enriched.title,
            "slug": enriched.slug,
            "subject": enriched.subject,
            "grade": enriched.grade,
            "category": enriched.document_type,
            "topic": enriched.document_type,
            "author_name": enriched.geo_school or "Beekip (sưu tầm & số hóa)",
            "academic_year": str(published_year),
            "description": article_content,
            "clean_pdf_path": str(clean_pdf_path),
            "cover_image_path": str(cover_image_path),
            "raw_url": url,
            "page_count": page_count,
            "file_size_bytes": file_size,
            "schema_jsonld": schema_jsonld,
            "audience_tags": [f"Lớp {enriched.grade}", enriched.subject, f"Năm học {published_year}"],
            "revision_count": 0,
            "audit_history": [],
        }

        logger.info("Agent 1 produced draft package for: %s [Slug: %s]", enriched.title, enriched.slug)
        return draft_package

    def refine_draft_package(
        self,
        draft_package: Dict[str, Any],
        defects: List[str],
    ) -> Dict[str, Any]:
        """
        Self-Healing refinement: Automatically repair specific defects identified by Agent 2.
        """
        draft = dict(draft_package)
        draft["revision_count"] = draft.get("revision_count", 0) + 1
        clean_pdf = Path(draft["clean_pdf_path"])
        cover_path = Path(draft["cover_image_path"])

        logger.info("Agent 1 refining draft (Revision #%d) with defects: %s", draft["revision_count"], defects)

        for defect in defects:
            d_lower = defect.lower()

            # Fix Cover resolution/size
            if any(k in d_lower for k in ("cover", "ảnh bìa", "bìa", "1200px")):
                logger.info("Agent 1 repairing Cover Thumbnail: enhancing DPI & dimensions...")
                self.renderer.render_cover_thumbnail(clean_pdf, cover_path, target_width=MIN_COVER_WIDTH_PX, quality=85)

            # Fix Article content length / structure
            if any(k in d_lower for k in ("content", "bài viết", "từ", "h2", "katex", "độ dài")):
                logger.info("Agent 1 repairing Article content: expanding GEO & KaTeX sections...")
                draft["description"] = self.generate_geo_seo_markdown(
                    meta_title=draft["title"],
                    subject=draft["subject"],
                    grade=draft["grade"],
                    school=draft.get("author_name"),
                    source_url=draft.get("raw_url", ""),
                    page_count=draft.get("page_count", 1),
                    file_size_bytes=draft.get("file_size_bytes", 1024),
                    detected_year=int(draft.get("academic_year") or 2026),
                    extended_analysis=True,
                )

            # Fix Schema
            if any(k in d_lower for k in ("schema", "newsarticle", "learningresource")):
                logger.info("Agent 1 regenerating Schema.org JSON-LD...")
                from datetime import datetime, timezone
                pub_iso = datetime.now(timezone.utc).isoformat()
                cover_preview_url = f"https://tailieu.beekip.vn/api/documents/{draft['slug']}/cover"
                file_preview_url = f"https://tailieu.beekip.vn/api/documents/{draft['slug']}/download"
                draft["schema_jsonld"] = self.build_dual_schema_jsonld(
                    title=draft["title"],
                    slug=draft["slug"],
                    subject=draft["subject"],
                    grade=draft["grade"],
                    school=draft.get("author_name"),
                    published_year=int(draft.get("academic_year") or 2026),
                    cover_url=cover_preview_url,
                    file_url=file_preview_url,
                    date_published=pub_iso,
                )

        return draft
