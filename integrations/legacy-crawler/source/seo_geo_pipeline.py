import argparse
from html import escape
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import pypdf

from config import DATA_DIR, BRAND_NAME, BRAND_DOMAIN, BRAND_URL, BRAND_FULL_NAME
from database import get_connection, init_db
from geo_entity_extractor import extract_geo_and_metadata, remove_accents

# Cấu hình logging
logger = logging.getLogger("SEOGeoPipeline")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.getLogger("pypdf").setLevel(logging.ERROR)

# Thư mục đích lưu trữ tài liệu chuẩn SEO & GEO
KHOAHOC_DIR = DATA_DIR / "TaiLieu_KhoaHoc"
SEO_GEO_DIR = DATA_DIR / "TaiLieu_Chuan_SEO_GEO"
SEO_GEO_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def make_seo_slug_and_filename(title: str, post_id: int, extension: str, brand_tag: str = "tailieu-beekip") -> Tuple[str, str]:
    """
    Tạo slug URL và tên file chuẩn SEO Google:
    - Loại bỏ dấu tiếng Việt, ký tự đặc biệt
    - Nối từ bằng dấu gạch ngang (-)
    - Gắn kèm hậu tố thương hiệu Beekip và post_id để đảm bảo tính duy nhất tuyệt đối
    """
    clean_text = remove_accents(title).lower()
    clean_text = re.sub(r'[^a-z0-9\s-]', '', clean_text)
    clean_text = re.sub(r'[\s_]+', '-', clean_text).strip('-')

    if len(clean_text) > 70:
        clean_text = clean_text[:70].rsplit('-', 1)[0]

    slug = f"{clean_text}-id{post_id}"
    ext = extension.lower().strip('.')
    filename = f"{clean_text}-{brand_tag}-id{post_id}.{ext}"
    return slug, filename

def build_seo_titles_and_meta(original_title: str, geo_info: Dict[str, Any]) -> Dict[str, str]:
    """Sinh Meta Title và Meta Description chuẩn SEO Google (tối ưu CTR và ký tự)."""
    prov = geo_info.get("geo_province", "")
    school = geo_info.get("geo_school", "")
    grade = geo_info.get("grade_name", "THPT")
    doc_type = geo_info.get("doc_type", "Tài liệu môn Toán")
    year = geo_info.get("academic_year", "")

    # 1. SEO Title H1 (đầy đủ, trang trọng)
    seo_title = f"{original_title} (Có Đáp Án Chi Tiết) | {BRAND_NAME}"

    # 2. Meta Title (50-60 ký tự)
    meta_entity = school if school else (f"Sở {prov}" if prov not in ["Toàn Quốc", "Quốc Tế"] else "")
    if meta_entity:
        short_title = f"{doc_type} Toán {grade} {meta_entity} (Đáp Án) | {BRAND_NAME}"
    else:
        clean_t = re.sub(r'\s*[-–|].*$', '', original_title).strip()
        short_title = f"{clean_t[:42]} (Có Đáp Án) | {BRAND_NAME}"

    if len(short_title) > 65:
        meta_title = short_title[:60].rsplit(' ', 1)[0] + f" | {BRAND_NAME}"
    else:
        meta_title = short_title

    # 3. Meta Description (150-160 ký tự chuẩn Google snippet)
    entity_desc = f" của {school or prov}" if (school or (prov and prov not in ["Toàn Quốc", "Quốc Tế"])) else ""
    meta_desc = (
        f"Tải miễn phí trọn bộ {original_title}{entity_desc} kèm đáp án và hướng dẫn giải chi tiết. "
        f"Tài liệu ôn thi Toán {grade} chuẩn cấu trúc Bộ GD&ĐT tại {BRAND_DOMAIN}."
    )
    if len(meta_desc) > 165:
        meta_description = meta_desc[:157].rsplit(' ', 1)[0] + "..."
    else:
        meta_description = meta_desc

    return {
        "seo_title": seo_title,
        "meta_title": meta_title,
        "meta_description": meta_description
    }

def generate_semantic_html(original_title: str, seo_title: str, geo_info: Dict[str, Any], download_filename: str) -> str:
    """Xây dựng nội dung bài viết HTML độc bản, giàu tính sư phạm, chống trùng lặp theo chuẩn E-E-A-T."""
    original_title = escape(original_title)
    seo_title = escape(seo_title)
    download_filename = escape(download_filename)
    geo_info = {key: escape(value) if isinstance(value, str) else value for key, value in geo_info.items()}
    grade = geo_info.get("grade_name", "THPT")
    prov = geo_info.get("geo_province", "Toàn quốc")
    region = geo_info.get("geo_region", "Toàn quốc")
    school = geo_info.get("geo_school", "")
    year = geo_info.get("academic_year", "2025 - 2026")
    doc_type = geo_info.get("doc_type", "Tài liệu ôn tập")
    authority = geo_info.get("geo_authority", "")
    issuer = school or authority or f"Hội đồng chuyên môn {prov}" if prov != "Toàn Quốc" else "Ban chuyên môn Toán học Beekip"

    faq_items = [
        (f"Tài liệu {original_title} có kèm đáp án chi tiết không?",
         "Có. Tài liệu cung cấp đầy đủ bảng đáp án trắc nghiệm hoặc hướng dẫn giải từng bước chi tiết cho các bài toán tự luận, thuận tiện cho học sinh tự học và giáo viên tra cứu."),
        (f"Làm thế nào để tải về file PDF của bộ đề này?",
         f"Bạn có thể nhấn trực tiếp vào nút 'Tải bản PDF' phía dưới để tải toàn bộ tệp tài liệu nguyên bản hoàn toàn miễn phí từ hệ thống {BRAND_DOMAIN} mà không cần đăng ký tài khoản."),
        (f"Tài liệu này áp dụng cho chương trình học nào?",
         f"Bộ tài liệu được thiết kế bám sát theo chuẩn kiến thức và kỹ năng của Chương trình GDPT mới (các bộ sách Kết nối tri thức, Cánh diều, Chân trời sáng tạo) môn Toán {grade}.")
    ]

    faq_html = "\n".join([
        f"""        <div class="faq-item" itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
            <h3 class="text-base font-semibold text-slate-800" itemprop="name">{q}</h3>
            <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
                <p class="text-sm text-slate-600 mt-1" itemprop="text">{a}</p>
            </div>
        </div>""" for q, a in faq_items
    ])

    html = f"""<div class="beekip-document-content font-sans text-slate-700 leading-relaxed">
    <div class="doc-badge-bar flex flex-wrap gap-2 mb-4">
        <span class="badge bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs px-2.5 py-1 rounded font-medium">Toán {grade}</span>
        <span class="badge bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs px-2.5 py-1 rounded font-medium">{doc_type}</span>
        <span class="badge bg-amber-50 text-amber-700 border border-amber-200 text-xs px-2.5 py-1 rounded font-medium">Năm học {year}</span>
        <span class="badge bg-sky-50 text-sky-700 border border-sky-200 text-xs px-2.5 py-1 rounded font-medium">📍 {prov} ({region})</span>
    </div>

    <section class="doc-intro mb-6">
        <p>Nhằm phục vụ công tác giảng dạy, học tập và ôn thi môn Toán chất lượng cao, <strong>{BRAND_FULL_NAME}</strong> trân trọng chia sẻ tới quý thầy cô và các em học sinh tài liệu: <strong>{seo_title}</strong>. Đây là tư liệu quý giá được số hóa, kiểm duyệt nội dung và tối ưu cấu trúc theo quy chuẩn khảo thí hiện hành.</p>
    </section>

    <h2 class="text-lg font-bold text-slate-900 border-b border-slate-200 pb-2 mb-3">1. Thông tin tổng quan tài liệu</h2>
    <div class="doc-summary-table overflow-x-auto mb-6">
        <table class="w-full text-sm text-left border border-slate-200 rounded-lg">
            <tbody class="divide-y divide-slate-200">
                <tr class="bg-slate-50"><td class="py-2 px-3 font-semibold w-1/3">Tên tài liệu</td><td class="py-2 px-3">{original_title}</td></tr>
                <tr><td class="py-2 px-3 font-semibold">Khối lớp / Cấp học</td><td class="py-2 px-3">Môn Toán {grade}</td></tr>
                <tr class="bg-slate-50"><td class="py-2 px-3 font-semibold">Đơn vị / Trường biên soạn</td><td class="py-2 px-3">{issuer}</td></tr>
                <tr><td class="py-2 px-3 font-semibold">Khu vực / Tỉnh thành (GEO)</td><td class="py-2 px-3">{prov} - {region}</td></tr>
                <tr class="bg-slate-50"><td class="py-2 px-3 font-semibold">Năm học áp dụng</td><td class="py-2 px-3">{year}</td></tr>
                <tr><td class="py-2 px-3 font-semibold">Hình thức tài liệu</td><td class="py-2 px-3">PDF chuẩn in ấn sắc nét + Có đáp án giải chi tiết</td></tr>
                <tr class="bg-slate-50"><td class="py-2 px-3 font-semibold">Biên tập &amp; Bảo trợ số</td><td class="py-2 px-3"><a href="{BRAND_URL}" class="text-indigo-600 font-medium hover:underline">{BRAND_DOMAIN}</a></td></tr>
            </tbody>
        </table>
    </div>

    <h2 class="text-lg font-bold text-slate-900 border-b border-slate-200 pb-2 mb-3">2. Đánh giá ma trận &amp; Mức độ phân hóa đề thi</h2>
    <p class="mb-3">Tài liệu được xây dựng với ma trận kiến thức khoa học, phân định rõ ràng các mức độ nhận thức theo định hướng đánh giá năng lực:</p>
    <ul class="list-disc pl-5 space-y-1.5 mb-6 text-sm">
        <li><strong>Mức độ Nhận biết &amp; Thông hiểu (50% - 60%):</strong> Bao quát các khái niệm, định lý trọng tâm, giúp học sinh củng cố vững chắc nền tảng lý thuyết và đạt điểm cơ bản nhanh chóng.</li>
        <li><strong>Mức độ Vận dụng (20% - 30%):</strong> Đòi hỏi kỹ năng kết hợp nhiều bước giải, biến đổi đại số linh hoạt và tư duy hình học không gian trực quan.</li>
        <li><strong>Mức độ Vận dụng cao (10% - 20%):</strong> Các bài toán thực tiễn phân hóa cao, các bài toán bất đẳng thức, cực trị hoặc phương pháp tọa độ mang tính chọn lọc học sinh giỏi.</li>
    </ul>

    <h2 class="text-lg font-bold text-slate-900 border-b border-slate-200 pb-2 mb-3">3. Lời khuyên ôn luyện và phương pháp tự làm đề</h2>
    <ol class="list-decimal pl-5 space-y-2 mb-6 text-sm">
        <li><strong>Làm bài bấm giờ nghiêm túc:</strong> Tạo áp lực thời gian giống như thi thật để rèn luyện tâm lý vững vàng và kỹ năng phân bổ thời lượng hợp lý.</li>
        <li><strong>Đối chiếu đáp án và ghi chép lỗi sai:</strong> Sau khi hoàn thành, hãy tra cứu kỹ lời giải chi tiết, phân tích nguyên nhân các câu làm sai để tránh lặp lại.</li>
        <li><strong>Hệ thống hóa chuyên đề:</strong> Tổng hợp các dạng toán khó vào sổ tay cá nhân để ôn luyện ngắt quãng định kỳ.</li>
    </ol>

    <div class="download-box my-6 p-4 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
            <h4 class="font-bold text-slate-900 text-sm">Tải về tệp tài liệu gốc đính kèm:</h4>
            <p class="text-xs text-slate-600 mt-0.5">{download_filename}</p>
        </div>
        <div class="shrink-0">
            <span class="inline-block bg-indigo-600 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm">Tải PDF Miễn Phí</span>
        </div>
    </div>

    <h2 class="text-lg font-bold text-slate-900 border-b border-slate-200 pb-2 mb-3">4. Câu hỏi thường gặp (FAQ)</h2>
    <div class="faq-section space-y-3 mb-6" itemscope itemtype="https://schema.org/FAQPage">
{faq_html}
    </div>
</div>"""
    return html.strip()

def build_schema_jsonld(original_title: str, seo_title: str, slug: str, meta_description: str, geo_info: Dict[str, Any], date_str: str) -> Dict[str, Any]:
    """Tạo Schema.org JSON-LD đa tầng (@graph) tối ưu cho Google Rich Results và AI Search (GEO)."""
    canonical_url = f"{BRAND_URL}/tai-lieu/{slug}"
    grade = geo_info.get("grade_name", "THPT")
    prov = geo_info.get("geo_province", "Toàn quốc")
    region = geo_info.get("geo_region", "Toàn quốc")
    school = geo_info.get("geo_school", "")

    graph = [
        {
            "@type": ["LearningResource", "DigitalDocument"],
            "@id": f"{canonical_url}#document",
            "name": seo_title,
            "description": meta_description,
            "learningResourceType": "Practice Test / Exam",
            "educationalLevel": f"Toán {grade}",
            "inLanguage": "vi-VN",
            "isAccessibleForFree": True,
            "datePublished": date_str,
            "publisher": {
                "@type": "Organization",
                "name": BRAND_FULL_NAME,
                "url": BRAND_URL,
                "logo": f"{BRAND_URL}/assets/logo.png"
            },
            "author": {
                "@type": "Organization",
                "name": school if school else (f"Sở GD&ĐT {prov}" if prov != "Toàn Quốc" else BRAND_NAME)
            }
        },
        {
            "@type": "BreadcrumbList",
            "@id": f"{canonical_url}#breadcrumb",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Trang chủ",
                    "item": BRAND_URL
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": f"Tài liệu Toán {grade}",
                    "item": f"{BRAND_URL}/chuyen-muc/toan-{grade.lower().replace(' ', '-')}"
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": seo_title,
                    "item": canonical_url
                }
            ]
        },
        {
            "@type": "FAQPage",
            "@id": f"{canonical_url}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"Tài liệu {original_title} có kèm đáp án chi tiết không?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Có. Tài liệu cung cấp đầy đủ bảng đáp án trắc nghiệm hoặc hướng dẫn giải từng bước chi tiết."
                    }
                },
                {
                    "@type": "Question",
                    "name": "Làm thế nào để tải về file PDF của bộ đề này?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": f"Bạn có thể tải trực tiếp file PDF miễn phí từ hệ thống {BRAND_DOMAIN} mà không cần đăng ký tài khoản."
                    }
                }
            ]
        }
    ]

    # Bổ sung GEO entity vào Schema nếu có tỉnh thành cụ thể
    if prov and prov not in ["Toàn Quốc", "Quốc Tế"]:
        graph.append({
            "@type": "Place",
            "@id": f"{canonical_url}#location",
            "name": f"{prov}, Việt Nam",
            "address": {
                "@type": "PostalAddress",
                "addressRegion": prov,
                "addressCountry": "VN"
            }
        })

    return {
        "@context": "https://schema.org",
        "@graph": graph
    }

def rewrite_pdf_binary_metadata(src_pdf_path: Path, dest_pdf_path: Path, seo_title: str, keywords: str) -> Tuple[bool, int, str]:
    """
    Ghi đè Metadata nhị phân của tệp PDF bằng pypdf:
    - Xóa metadata cũ của website gốc
    - Thiết lập Author, Title, Subject, Keywords chuẩn thương hiệu Beekip
    - Lưu vào thư mục chuẩn hóa SEO & GEO
    """
    try:
        with open(src_pdf_path, "rb") as f_chk:
            header = f_chk.read(5)
        if not header.startswith(b"%PDF"):
            dest_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_pdf_path, dest_pdf_path)
            return True, dest_pdf_path.stat().st_size, "Copied non-PDF file"

        reader = pypdf.PdfReader(str(src_pdf_path))
        writer = pypdf.PdfWriter()
        writer.append(reader)

        new_metadata = {
            "/Title": seo_title,
            "/Author": f"{BRAND_FULL_NAME} ({BRAND_DOMAIN})",
            "/Subject": f"Tài liệu ôn thi và bồi dưỡng môn Toán được số hóa và kiểm định bởi {BRAND_DOMAIN}",
            "/Keywords": keywords,
            "/Creator": f"{BRAND_DOMAIN} Educational Platform",
            "/Producer": f"{BRAND_FULL_NAME} PDF SEO Engine"
        }
        writer.add_metadata(new_metadata)

        dest_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_pdf_path, "wb") as f_out:
            writer.write(f_out)

        out_size = dest_pdf_path.stat().st_size
        return True, out_size, ""
    except Exception as e:
        # Nếu lỗi parse (ví dụ file bị encrypt hoặc lỗi cấu trúc), sao chép nguyên bản để bảo toàn tài liệu
        try:
            dest_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_pdf_path, dest_pdf_path)
            return True, dest_pdf_path.stat().st_size, f"Fallback copy: {e}"
        except Exception as e2:
            return False, 0, str(e2)

def process_single_document(row: Dict[str, Any]) -> Dict[str, Any]:
    """Xử lý toàn diện 1 tài liệu qua toàn bộ 5 tầng chuẩn hóa SEO & GEO."""
    post_id = row["post_id"]
    title = row["original_title"]
    orig_url = row.get("original_url")
    target_folder = row.get("target_folder") or "3_THPT/Chung"
    raw_pdf_path = row.get("pdf_path")
    raw_word_path = row.get("word_path")
    source_site = row.get("source_site", "toanmath")
    crawled_at = row.get("crawled_at") or datetime.now().isoformat()
    categories = json.loads(row.get("categories", "[]")) if isinstance(row.get("categories"), str) else (row.get("categories") or [])

    # TẦNG 1: Trích xuất thực thể GEO và siêu dữ liệu sư phạm
    geo_info = extract_geo_and_metadata(title, categories)
    prov = geo_info["geo_province"]
    school = geo_info["geo_school"]
    year = geo_info["academic_year"]
    grade_name = geo_info["grade_name"]
    doc_type = geo_info["doc_type"]

    # TẦNG 2: Sinh tiêu đề chuẩn SEO, Meta Description và HTML Content
    seo_meta = build_seo_titles_and_meta(title, geo_info)
    seo_title = seo_meta["seo_title"]
    meta_title = seo_meta["meta_title"]
    meta_description = seo_meta["meta_description"]

    # Tạo Slug và Tên file chuẩn SEO
    slug, seo_pdf_filename = make_seo_slug_and_filename(title, post_id, "pdf")
    _, seo_word_filename = make_seo_slug_and_filename(title, post_id, "docx")

    # TẦNG 3: Chuẩn hóa tệp nhị phân PDF & Word
    dest_folder = SEO_GEO_DIR / target_folder
    dest_folder.mkdir(parents=True, exist_ok=True)

    dest_pdf_path = None
    dest_word_path = None
    final_file_size = 0
    file_err = ""

    # 1. Xử lý tệp PDF
    if raw_pdf_path and os.path.exists(raw_pdf_path):
        src_p = Path(raw_pdf_path)
        dest_p = dest_folder / seo_pdf_filename
        keywords_str = f"Toán {grade_name}, {doc_type}, {prov}, {school}, {BRAND_NAME}, {BRAND_DOMAIN}"
        ok, sz, err = rewrite_pdf_binary_metadata(src_p, dest_p, seo_title, keywords_str)
        if ok:
            dest_pdf_path = str(dest_p)
            final_file_size += sz
        else:
            file_err = err

    # 2. Xử lý tệp Word nếu có
    if raw_word_path and os.path.exists(raw_word_path):
        src_w = Path(raw_word_path)
        ext = src_w.suffix.lstrip('.')
        _, seo_word_fn = make_seo_slug_and_filename(title, post_id, ext)
        dest_w = dest_folder / seo_word_fn
        try:
            shutil.copy2(src_w, dest_w)
            dest_word_path = str(dest_w)
            final_file_size += dest_w.stat().st_size
        except Exception:
            pass

    # TẦNG 4: Sinh Semantic HTML và Schema.org JSON-LD
    chosen_filename = seo_pdf_filename if dest_pdf_path else (seo_word_filename if dest_word_path else "tailieu.pdf")
    content_html = generate_semantic_html(title, seo_title, geo_info, chosen_filename)
    schema_jsonld = build_schema_jsonld(title, seo_title, slug, meta_description, geo_info, crawled_at)

    # Đóng gói Payload hoàn chỉnh chuẩn Beekip
    payload = {
        "post_id": post_id,
        "original_title": title,
        "original_url": orig_url,
        "source_site": source_site,
        "seo_title": seo_title,
        "meta_title": meta_title,
        "meta_description": meta_description,
        "slug": slug,
        "level": row.get("level"),
        "grade": row.get("grade"),
        "grade_name": grade_name,
        "category_type": row.get("category_type"),
        "doc_type": doc_type,
        "target_folder": target_folder,
        "academic_year": year,
        "geo": {
            "province": prov,
            "region": geo_info["geo_region"],
            "school": school,
            "authority": geo_info["geo_authority"]
        },
        "content_html": content_html,
        "description_format": "html",
        "metadata_review_status": geo_info.get("metadata_review_status", "needs_review"),
        "metadata_evidence": geo_info.get("geo_evidence", []),
        "geo_rule_version": geo_info.get("geo_rule_version", "province-full-alias-v1"),
        "schema_jsonld": schema_jsonld,
        "pdf_file": dest_pdf_path,
        "word_file": dest_word_path,
        "file_size_bytes": final_file_size,
        "processed_at": datetime.now().isoformat()
    }

    # Lưu file metadata JSON đồng hành cùng tệp
    meta_dest = dest_folder / f"{slug}_meta.json"
    try:
        with open(meta_dest, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return {
        "post_id": post_id,
        "seo_title": seo_title,
        "slug": slug,
        "geo_province": prov,
        "geo_school": school,
        "academic_year": year,
        "meta_description": meta_description,
        "seo_file_path": dest_pdf_path or dest_word_path,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "status": "seo_processed",
        "file_size": final_file_size,
        "error": file_err
    }

def run_pipeline(limit: Optional[int] = None, max_workers: int = 24, use_multiprocess: bool = True):
    """Thực thi toàn bộ tiến trình chuẩn hóa SEO & GEO đa tiến trình / đa luồng."""
    init_db()
    conn = get_connection()
    c = conn.cursor()

    query = """
    SELECT post_id, original_url, original_title, slug, categories,
           level, grade, category_type, target_folder, pdf_path, word_path,
           source_site, crawled_at
    FROM crawled_posts
    WHERE status = 'downloaded' AND (pdf_path IS NOT NULL OR word_path IS NOT NULL)
    ORDER BY post_id DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    c.execute(query)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    total_items = len(rows)
    engine_name = "ProcessPool (Multi-Core)" if use_multiprocess else "ThreadPool"
    logger.info("=" * 65)
    logger.info(f"🚀 KHỞI ĐỘNG PIPELINE CHUẨN HÓA SEO & GEO BEEKIP")
    logger.info(f"Tổng số tài liệu cần xử lý: {total_items:,} (Engine={engine_name}, Workers={max_workers})")
    logger.info(f"Thư mục đầu ra: {SEO_GEO_DIR}")
    logger.info("=" * 65)

    if total_items == 0:
        logger.info("Không có tài liệu nào đang chờ xử lý SEO!")
        return

    t_start = time.time()
    processed_count = 0
    total_bytes = 0
    update_batch = []

    ExecutorClass = ProcessPoolExecutor if use_multiprocess else ThreadPoolExecutor
    with ExecutorClass(max_workers=max_workers) as executor:
        future_to_row = {executor.submit(process_single_document, row): row for row in rows}

        for idx, future in enumerate(as_completed(future_to_row), start=1):
            try:
                res = future.result()
                processed_count += 1
                total_bytes += res["file_size"]

                update_batch.append((
                    res["seo_title"],
                    res["slug"],
                    res["geo_province"],
                    res["geo_school"],
                    res["academic_year"],
                    res["meta_description"],
                    res["seo_file_path"],
                    res["payload_json"],
                    datetime.now().isoformat(),
                    res["post_id"]
                ))

                if idx % 100 == 0 or idx == total_items:
                    elapsed = max(time.time() - t_start, 0.5)
                    speed = idx / elapsed
                    mb = total_bytes / (1024 * 1024)
                    logger.info(
                        f"[{idx:5d}/{total_items}] ({idx/total_items*100:5.1f}%) | "
                        f"Tốc độ: {speed * 60:.0f} bài/phút | "
                        f"Dung lượng tối ưu: {mb:.1f} MB | "
                        f"Đã cập nhật DB: {len(update_batch)} bài"
                    )

                if len(update_batch) >= 100:
                    c_conn = get_connection()
                    c_cur = c_conn.cursor()
                    c_cur.executemany("""
                    UPDATE crawled_posts SET
                        seo_title = ?, slug = ?, geo_province = ?, geo_school = ?,
                        academic_year = ?, meta_description = ?, seo_file_path = ?,
                        payload_json = ?, status = 'seo_processed', seo_processed_at = ?
                    WHERE post_id = ?
                    """, update_batch)
                    c_conn.commit()
                    c_conn.close()
                    update_batch = []

            except Exception as e:
                logger.error(f"Lỗi future: {e}")

        if update_batch:
            c_conn = get_connection()
            c_cur = c_conn.cursor()
            c_cur.executemany("""
            UPDATE crawled_posts SET
                seo_title = ?, slug = ?, geo_province = ?, geo_school = ?,
                academic_year = ?, meta_description = ?, seo_file_path = ?,
                payload_json = ?, status = 'seo_processed', seo_processed_at = ?
            WHERE post_id = ?
            """, update_batch)
            c_conn.commit()
            c_conn.close()

    total_time = time.time() - t_start
    total_gb = total_bytes / (1024**3)
    logger.info("=" * 65)
    logger.info(f"🎉 HOÀN THÀNH PIPELINE CHUẨN HÓA SEO & GEO!")
    logger.info(f"Tổng tài liệu đã tối ưu: {processed_count:,}/{total_items:,} bài")
    logger.info(f"Thời gian xử lý: {total_time:.1f}s (~{total_time/60:.1f} phút)")
    logger.info(f"Tổng dung lượng kho chuẩn hóa: {total_gb:.2f} GB")
    logger.info("=" * 65)

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Pipeline Chuẩn Hóa SEO & GEO Beekip")
    parser.add_argument("--pilot", type=int, default=None, help="Chạy thử nghiệm số lượng bài viết (ví dụ: --pilot 500)")
    parser.add_argument("--all", action="store_true", help="Chạy toàn bộ tài liệu")
    parser.add_argument("--workers", type=int, default=24, help="Số tiến trình CPU xử lý song song (mặc định: 24)")
    parser.add_argument("--thread", action="store_true", help="Sử dụng ThreadPool thay vì ProcessPool đa nhân")
    args = parser.parse_args()

    limit = args.pilot if args.pilot else (None if args.all else 500)
    run_pipeline(limit=limit, max_workers=args.workers, use_multiprocess=not args.thread)
