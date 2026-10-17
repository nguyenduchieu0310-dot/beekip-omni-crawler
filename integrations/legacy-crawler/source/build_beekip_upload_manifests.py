from cloudflare.document_ingest import source_provenance
"""
build_beekip_upload_manifests.py
Tạo manifest CSV chuẩn định dạng Beekip cho toàn bộ 15.391 tài liệu đã chuẩn hóa SEO & GEO.
Phân chia thành 4 đợt (Phases) theo khối lớp và 1 tệp Master.
"""

import os
import csv
import json
import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ProcessPoolExecutor, as_completed
import pypdf

from config import DATA_DIR

DB_PATH = DATA_DIR / "crawler_state.db"
SEO_GEO_DIR = DATA_DIR / "TaiLieu_Chuan_SEO_GEO"
MANIFESTS_DIR = DATA_DIR / "manifests"
MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

CSV_HEADERS = [
    "stable_short_id",
    "document_code",
    "title",
    "slug",
    "authorName",
    "audienceTags",
    "shortDescription",
    "description",
    "descriptionFormat",
    "provenanceJson",
    "pdf_filename",
    "pdf_path",
    "mimeType",
    "sizeBytes",
    "sha256",
    "pageCount",
    "previewMode",
    "previewRanges",
    "watermarkEnabled",
    "downloadLimit",
    "isPublished",
    "orderIndex",
    "onlinePrice",
    "downloadPrice",
    "onlineStatus",
    "downloadStatus",
    "publish_mode",
    "robots_directive",
    "source_asset_variant",
    "scan_clean",
    "render_qa_pass",
    "pii_clean",
    "single_account_approval",
    "automatic_google_indexing"
]

def calculate_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def process_manifest_item(row: Dict[str, Any]) -> Dict[str, Any]:
    post_id = row["post_id"]
    slug = row["slug"]
    seo_title = row["seo_title"] or row["original_title"]
    short_desc = (row["meta_description"] or "")[:500]
    payload = json.loads(row["payload_json"]) if row.get("payload_json") else {}

    level = row.get("level") or "3_THPT"
    grade = row.get("grade") or "Lop_12"
    doc_type = payload.get("doc_type") or "Đề thi & Tài liệu ôn tập"
    prov = row.get("geo_province") or "Toàn Quốc"
    school = row.get("geo_school") or ""

    subject = row.get("subject") or "toan"
    subject_map = {
        "toan": ("Toán", "TOAN"),
        "vat_ly": ("Vật lý", "VATLY"),
        "hoa_hoc": ("Hóa học", "HOAHOC"),
        "sinh_hoc": ("Sinh học", "SINHHOC"),
        "tieng_anh": ("Tiếng Anh", "TIENGANH"),
        "ngu_van": ("Ngữ văn", "NGUVAN"),
        "lich_su": ("Lịch sử", "LICHSU"),
        "dia_ly": ("Địa lý", "DIALY"),
        "tin_hoc": ("Tin học", "TINHOC")
    }
    subj_title, subj_code = subject_map.get(subject, ("Toán", "TOAN"))

    tags = [f"{subj_title} {grade.replace('Lop_', 'Lớp ')}", doc_type]
    if prov and prov not in ["Toàn Quốc", "Quốc Tế"]:
        tags.append(prov)
    if school:
        tags.append(school)

    pdf_path_str = row.get("seo_file_path")
    pdf_p = Path(pdf_path_str) if pdf_path_str and os.path.exists(pdf_path_str) else None

    # Fallback tìm trong folder nếu seo_file_path bị lệch
    if not pdf_p or not pdf_p.exists():
        target_folder = row.get("target_folder") or ""
        expected = SEO_GEO_DIR / target_folder / f"{slug}-tailieu-beekip-id{post_id}.pdf"
        if expected.exists():
            pdf_p = expected

    size_b = 0
    sha_str = ""
    pages = 1

    if pdf_p and pdf_p.exists():
        size_b = pdf_p.stat().st_size
        sha_str = calculate_sha256(pdf_p)
        try:
            reader = pypdf.PdfReader(str(pdf_p))
            pages = max(len(reader.pages), 1)
        except Exception:
            pages = 1

    desc_html = payload.get("content_html") or ""
    if not desc_html or len(desc_html) > 12_000 or len(seo_title) > 200 or len(row.get("meta_description") or "") > 500:
        raise ValueError("Complete content is missing or exceeds the ingest contract; do not truncate it")
    provenance, _ = source_provenance(payload.get("original_url") or row.get("original_url") or "",
                                     payload.get("original_title") or row.get("original_title") or "",
                                     desc_html, payload.get("source_site") or row.get("source_site"), post_id, payload)

    return {
        "stable_short_id": f"bk{post_id}",
        "document_code": f"BK-{subj_code}-{grade.upper()}-ID{post_id}",
        "title": seo_title[:200],
        "slug": slug,
        "authorName": "Beekip Education",
        "audienceTags": json.dumps(tags, ensure_ascii=False),
        "shortDescription": short_desc,
        "description": desc_html,
        "descriptionFormat": payload.get("description_format", "html"),
        "provenanceJson": json.dumps(provenance, ensure_ascii=False),
        "pdf_filename": pdf_p.name if pdf_p else f"{slug}.pdf",
        "pdf_path": str(pdf_p) if pdf_p else "",
        "mimeType": "application/pdf",
        "sizeBytes": size_b,
        "sha256": sha_str,
        "pageCount": pages,
        "previewMode": "first_n_pages",
        "previewRanges": f"1-{min(pages, 5)}",
        "watermarkEnabled": "true",
        "downloadLimit": "3",
        "isPublished": "true",
        "orderIndex": "99999",
        "onlinePrice": "0",
        "downloadPrice": "0",
        "onlineStatus": "active",
        "downloadStatus": "active",
        "publish_mode": "live",
        "robots_directive": "index, follow",
        "source_asset_variant": "clean_digital",
        "scan_clean": (payload.get("qa") or {}).get("scan_clean", "unverified"),
        "render_qa_pass": "pending",
        "pii_clean": (payload.get("qa") or {}).get("pii_clean", "unverified"),
        "single_account_approval": "false",
        "automatic_google_indexing": "false",
        "level": level,
        "grade": grade,
        "post_id": post_id
    }

def main():
    print("=" * 70)
    print("🚀 BẮT ĐẦU XÂY DỰNG BỘ MANIFEST UPLOAD BEEKIP (15.391 TÀI LIỆU)")
    print("=" * 70)

    import argparse
    parser = argparse.ArgumentParser(description="Beekip Manifest Builder")
    parser.add_argument("--output", type=str, default=None, help="Tên file manifest xuất ra (ví dụ: manifest_vatly_pilot.csv)")
    parser.add_argument("--source-site", type=str, default=None, help="Lọc theo nguồn (ví dụ: thuvienvatly)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = """
    SELECT post_id, slug, original_title, seo_title, meta_description,
           level, grade, target_folder, geo_province, geo_school,
           seo_file_path, payload_json, subject, original_url, source_site
    FROM crawled_posts
    WHERE status = 'seo_processed'
    """
    params = []
    if args.source_site:
        query += " AND source_site = ?"
        params.append(args.source_site)
    query += " ORDER BY post_id DESC"

    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    total = len(rows)
    print(f"Tổng tài liệu cần đóng gói manifest: {total:,}")
    if total == 0:
        print("Không có tài liệu nào đang ở trạng thái 'seo_processed'.")
        return

    t0 = time.time()
    manifest_rows = []

    with ProcessPoolExecutor(max_workers=min(20, max(1, total))) as executor:
        future_to_row = {executor.submit(process_manifest_item, row): row for row in rows}
        for idx, future in enumerate(as_completed(future_to_row), start=1):
            res = future.result()
            manifest_rows.append(res)
            if idx % 1000 == 0 or idx == total:
                elapsed = max(time.time() - t0, 0.5)
                print(f"[{idx:5d}/{total}] ({idx/total*100:5.1f}%) | Tốc độ: {idx/elapsed*60:.0f} dòng/phút")

    print(f"\nĐã tính toán xong SHA256 và trang cho {len(manifest_rows):,} tài liệu!")

    def write_csv(filepath: Path, items: List[Dict[str, Any]]):
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(items)
        print(f"✅ Đã xuất: {filepath.name} ({len(items):,} tài liệu)")

    if args.output:
        out_path = MANIFESTS_DIR / args.output if not Path(args.output).is_absolute() else Path(args.output)
        write_csv(out_path, manifest_rows)
    else:
        # Phân loại theo 4 đợt (Phases)
        phase1_lop12 = []
        phase2_lop11_lop10 = []
        phase3_thcs = []
        phase4_tieuhoc = []

        for item in manifest_rows:
            lvl = item.get("level", "")
            grd = item.get("grade", "")

            if grd == "Lop_12":
                phase1_lop12.append(item)
            elif grd in ["Lop_11", "Lop_10"]:
                phase2_lop11_lop10.append(item)
            elif lvl == "2_THCS" or grd == "THPT_Chung":
                phase3_thcs.append(item)
            elif lvl == "1_Tieu_Hoc":
                phase4_tieuhoc.append(item)
            else:
                phase3_thcs.append(item)

        print("\nĐang xuất các tệp Manifest CSV...")
        write_csv(MANIFESTS_DIR / "manifest_phase1_lop12.csv", phase1_lop12)
        write_csv(MANIFESTS_DIR / "manifest_phase2_lop11_lop10.csv", phase2_lop11_lop10)
        write_csv(MANIFESTS_DIR / "manifest_phase3_thcs_va_chung.csv", phase3_thcs)
        write_csv(MANIFESTS_DIR / "manifest_phase4_tieuhoc.csv", phase4_tieuhoc)
        write_csv(MANIFESTS_DIR / "manifest_master_all_15391.csv", manifest_rows)

    print("\n" + "=" * 70)
    print("🎉 HOÀN THÀNH XÂY DỰNG TOÀN BỘ MANIFEST SẴN SÀNG UPLOAD!")
    print("=" * 70)

if __name__ == "__main__":
    main()
