from cloudflare.document_ingest import ingest_config, ingest_document, upload_document_asset
from legacy_document_ingest import payload_for_manifest_row
"""
beekip_wrangler_deployer.py - Tự động nạp tài liệu trực tiếp vào Cloudflare R2 & D1 qua Wrangler CLI
Hệ thống Beekip Education (tailieu.beekip.vn)
"""

import os
import sys
import csv
import json
import time
import uuid
import logging
import argparse
import subprocess
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from config import DATA_DIR

DB_PATH = DATA_DIR / "crawler_state.db"
MANIFESTS_DIR = DATA_DIR / "manifests"
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

WRANGLER_JS = r"C:\Users\Hieu Maico\AppData\Roaming\npm\node_modules\wrangler\bin\wrangler.js"
TARGET_DB = "khai-phong-lms-staging"
TARGET_R2_BUCKET = "khai-phong-lms-staging-files"
ADMIN_USER_ID = "0a06cb29-9889-4419-9d86-cb09b07df18e"
STORAGE_PREFIX = "documents/v1/"

logger = logging.getLogger("WranglerDeployer")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def sql_quote(val):
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''")
    return f"'{s}'"

from concurrent.futures import ThreadPoolExecutor, as_completed

REAL_PDF_MAP: Dict[str, Path] = {}
def get_real_pdf_map() -> Dict[str, Path]:
    global REAL_PDF_MAP
    if not REAL_PDF_MAP:
        seo_dir = DATA_DIR / "TaiLieu_Chuan_SEO_GEO"
        if seo_dir.exists():
            for p in seo_dir.rglob("*.pdf"):
                REAL_PDF_MAP[p.name] = p
    return REAL_PDF_MAP

def deploy_batch(rows: List[Dict[str, Any]], upload_workers: int = 12) -> Dict[str, Any]:
    """Upload tệp PDF lên R2 (đa luồng) và nạp dữ liệu D1 cho 1 lô tài liệu."""
    ingest_config()  # Fail before any R2 upload when the LMS transport is unavailable.
    valid_items = []
    file_map = get_real_pdf_map()

    for r in rows:
        slug = r["slug"]
        pdf_path = Path(r["pdf_path"])
        if not pdf_path.exists():
            if pdf_path.name in file_map:
                pdf_path = file_map[pdf_path.name]
                r["pdf_path"] = str(pdf_path)
            else:
                logger.warning(f"Bỏ qua do không thấy PDF: {pdf_path}")
                continue

        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://beekip.vn/document/{slug}"))
        file_uuid = str(uuid.uuid4())
        obj_key = f"{STORAGE_PREFIX}{doc_id}/{file_uuid}.pdf"
        r["_ingest_payload"] = payload_for_manifest_row(r, doc_id, obj_key)
        valid_items.append((r, doc_id, file_uuid, obj_key))

    if not valid_items:
        return {"uploaded": [], "error": ""}

    def upload_one_r2(item):
        r, doc_id, file_uuid, obj_key = item
        pdf_path = Path(r["pdf_path"])
        try:
            upload_document_asset(obj_key, pdf_path.read_bytes(), "application/pdf")
            return item, True, ""
        except Exception as exc:
            return item, False, type(exc).__name__ + ": " + str(exc)

    uploaded_items = []
    sql_statements = []
    now_ms = int(time.time() * 1000)

    with ThreadPoolExecutor(max_workers=upload_workers) as executor:
        futures = [executor.submit(upload_one_r2, it) for it in valid_items]
        for f in as_completed(futures):
            item, ok, err = f.result()
            r, doc_id, file_uuid, obj_key = item
            slug = r["slug"]
            post_id = r.get("post_id", 0)
            if not ok:
                logger.error(f"Lỗi tải lên R2 [{slug}]: {err[:200]}")
                continue

            try:
                ingest_document(r["_ingest_payload"])
            except Exception as exc:
                logger.error("LMS ingest failed for %s: %s", slug, type(exc).__name__)
                return {"uploaded": uploaded_items, "error": "LMS ingest rejected a document; see the source validation report"}
            uploaded_items.append((slug, post_id))

    return {"uploaded": uploaded_items, "error": ""}

def main():
    parser = argparse.ArgumentParser(description="Beekip Legacy Manifest Ingest Adapter")
    parser.add_argument("--manifest", type=str, default="manifest_phase1_lop12.csv", help="Tệp manifest trong data/manifests/")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số bài nạp")
    parser.add_argument("--batch-size", type=int, default=20, help="Số bài nạp mỗi lô SQL D1 (mặc định: 20)")
    args = parser.parse_args()

    m_path = MANIFESTS_DIR / args.manifest if not Path(args.manifest).is_absolute() else Path(args.manifest)
    if not m_path.exists():
        logger.error(f"Không tìm thấy manifest: {m_path}")
        return

    with open(m_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        sid = r.get("stable_short_id", "")
        r["post_id"] = int(sid[2:]) if sid.startswith("bk") and sid[2:].isdigit() else 0

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT post_id FROM crawled_posts WHERE status = 'uploaded'")
    already_uploaded = set(r[0] for r in c.fetchall())
    conn.close()

    pending = [r for r in rows if r["post_id"] not in already_uploaded]
    if args.limit:
        pending = pending[:args.limit]

    total = len(pending)
    logger.info("=" * 70)
    logger.info("🚀 KHỞI ĐỘNG BEEKIP LMS INGEST ADAPTER")
    logger.info(f"Manifest: {m_path.name}")
    logger.info(f"Tổng tài liệu cần nạp: {total:,} / {len(rows):,}")
    logger.info(f"Database: {TARGET_DB} | R2 Bucket: {TARGET_R2_BUCKET}")
    logger.info("=" * 70)

    if total == 0:
        logger.info("Tất cả tài liệu đã được nạp thành công!")
        return

    batch_size = args.batch_size
    t0 = time.time()
    total_uploaded = 0

    for i in range(0, total, batch_size):
        chunk = pending[i:i + batch_size]
        res = deploy_batch(chunk)
        successes = res.get("uploaded", [])
        if successes:
            total_uploaded += len(successes)
            c_conn = sqlite3.connect(DB_PATH)
            c_cur = c_conn.cursor()
            c_cur.executemany("""
            UPDATE crawled_posts SET status = 'uploaded', uploaded_at = ?
            WHERE post_id = ?
            """, [(datetime.now().isoformat(), p_id) for _, p_id in successes])
            c_conn.commit()
            c_conn.close()

        elapsed = max(time.time() - t0, 0.5)
        speed = total_uploaded / elapsed * 60
        logger.info(f"[{min(i + batch_size, total):5d}/{total}] Đã nạp thành công: {total_uploaded} | Tốc độ: {speed:.0f} bài/phút")

    logger.info("=" * 70)
    logger.info(f"🎉 HOÀN TẤT NẠP TÀI LIỆU QUA LMS INGEST: {total_uploaded:,} bài")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
