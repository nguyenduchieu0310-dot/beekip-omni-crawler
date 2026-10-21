from legacy_document_ingest import payload_for_manifest_row
"""
build_d1_sql_batches.py - Xuất toàn bộ 15.391 tài liệu thành các tệp SQL D1 độc lập
Hệ thống Beekip Education (tailieu.beekip.vn)
"""

import os
import csv
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

from config import DATA_DIR

MANIFESTS_DIR = DATA_DIR / "manifests"
SQL_DIR = DATA_DIR / "sql_d1_export"
SQL_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_USER_ID = "0a06cb29-9889-4419-9d86-cb09b07df18e"
STORAGE_PREFIX = "documents/v1/"

def sql_quote(val):
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''")
    return f"'{s}'"

def generate_sql_for_manifest(manifest_path: Path, output_sql_path: Path):
    print(f"Đang sinh SQL từ {manifest_path.name}...")
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    now_ms = int(time.time() * 1000)
    statements = []

    for r in rows:
        slug = r["slug"]
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://beekip.vn/document/{slug}"))
        file_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"file://{slug}"))
        obj_key = f"{STORAGE_PREFIX}{doc_id}/{file_uuid}.pdf"

        validated = payload_for_manifest_row(r, doc_id, obj_key)
        title = r["title"]
        code = r["document_code"][:50]
        author = r.get("authorName", "Beekip Education")
        audience_tags = r.get("audienceTags", "[]")
        short_desc = r.get("shortDescription", "")
        desc = r.get("description", "")
        orig_filename = r.get("pdf_filename", f"{slug}.pdf")[:180]
        size_b = int(r.get("sizeBytes", 0))
        pages = int(r.get("pageCount", 1))
        preview_pages = list(range(1, min(pages, 5) + 1))
        preview_json = json.dumps(preview_pages)

        # 1. Bảng documents
        statements.append(
            f"INSERT INTO documents ("
            f"id, document_code, slug, title, author_name, audience_tags_json, description_format, source_provenance_json, content_quality_json, "
            f"short_description, description, source_object_key, original_filename, "
            f"mime_type, size_bytes, page_count, preview_pages_json, watermark_enabled, "
            f"download_limit, is_published, order_index, created_by, updated_by, "
            f"created_at, updated_at, promo_video_title, promo_video_duration_seconds"
            f") VALUES ("
            f"{sql_quote(doc_id)}, {sql_quote(code)}, {sql_quote(slug)}, {sql_quote(title)}, "
            f"{sql_quote(author)}, {sql_quote(audience_tags)}, "
            f"{sql_quote(validated['document']['descriptionFormat'])}, {sql_quote(json.dumps(validated['provenance'], ensure_ascii=False))}, "
            f"{sql_quote(json.dumps(validated['quality'], ensure_ascii=False))}, {sql_quote(short_desc)}, "
            f"{sql_quote(desc)}, {sql_quote(obj_key)}, {sql_quote(orig_filename)}, "
            f"'application/pdf', {size_b}, {pages}, {sql_quote(preview_json)}, 1, "
            f"3, 1, 99999, {sql_quote(ADMIN_USER_ID)}, {sql_quote(ADMIN_USER_ID)}, "
            f"{now_ms}, {now_ms}, '', 90"
            f") ON CONFLICT(id) DO NOTHING;"
        )

        # 2. Bảng product_offers
        offer_online_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://beekip.vn/offer/online/{slug}"))
        offer_dl_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://beekip.vn/offer/download/{slug}"))

        statements.append(
            f"INSERT INTO product_offers ("
            f"id, product_type, product_id, title, price_vnd, currency, checkout_mode, sales_page_json, status, version, created_by, updated_by, created_at, updated_at"
            f") VALUES ("
            f"{sql_quote(offer_online_id)}, 'document_online', {sql_quote(doc_id)}, {sql_quote(f'{title} - Đọc online')}, 0, 'VND', 'quick', '{{}}', 'active', 1, {sql_quote(ADMIN_USER_ID)}, {sql_quote(ADMIN_USER_ID)}, {now_ms}, {now_ms}"
            f") ON CONFLICT(id) DO NOTHING;"
        )
        statements.append(
            f"INSERT INTO product_offers ("
            f"id, product_type, product_id, title, price_vnd, currency, checkout_mode, sales_page_json, status, version, created_by, updated_by, created_at, updated_at"
            f") VALUES ("
            f"{sql_quote(offer_dl_id)}, 'document_download', {sql_quote(doc_id)}, {sql_quote(f'{title} - Tải PDF')}, 0, 'VND', 'quick', '{{}}', 'active', 1, {sql_quote(ADMIN_USER_ID)}, {sql_quote(ADMIN_USER_ID)}, {now_ms}, {now_ms}"
            f") ON CONFLICT(id) DO NOTHING;"
        )

    with open(output_sql_path, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(statements))

    print(f"✅ Đã xuất: {output_sql_path.name} ({len(rows):,} tài liệu, {len(statements):,} câu lệnh SQL)")

def main():
    print("=" * 70)
    print("🚀 BẮT ĐẦU XUẤT SQL D1 CHO TOÀN BỘ 15.391 TÀI LIỆU BEEKIP")
    print("=" * 70)

    generate_sql_for_manifest(
        MANIFESTS_DIR / "manifest_phase1_lop12.csv",
        SQL_DIR / "phase1_lop12.sql"
    )
    generate_sql_for_manifest(
        MANIFESTS_DIR / "manifest_phase2_lop11_lop10.csv",
        SQL_DIR / "phase2_lop11_lop10.sql"
    )
    generate_sql_for_manifest(
        MANIFESTS_DIR / "manifest_phase3_thcs_va_chung.csv",
        SQL_DIR / "phase3_thcs_va_chung.sql"
    )
    generate_sql_for_manifest(
        MANIFESTS_DIR / "manifest_phase4_tieuhoc.csv",
        SQL_DIR / "phase4_tieuhoc.sql"
    )

    print("=" * 70)
    print("🎉 HOÀN THÀNH XUẤT TOÀN BỘ TỆP SQL D1 CHO BEEKIP!")
    print("=" * 70)

if __name__ == "__main__":
    main()
