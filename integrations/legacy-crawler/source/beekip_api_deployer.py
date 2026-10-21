from cloudflare.document_ingest import ingest_config, ingest_document, upload_document_asset
from legacy_document_ingest import payload_for_manifest_row
"""
beekip_api_deployer.py - Legacy manifest adapter for create-only LMS ingest
Hệ thống Beekip Education (tailieu.beekip.vn)
- Hiệu năng cao gấp 5-10x so với Wrangler CLI
- Không spawn tiến trình con (Zero child processes)
- Tránh hoàn toàn lỗi treo socket/pipe trên Windows
- Publication uses DOCUMENT_INGEST_TOKEN; no Cloudflare OAuth refresh or direct document SQL
"""

import os
import sys
import csv
import json
import time
import uuid
import logging
import argparse
import sqlite3
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import DATA_DIR

DB_PATH = DATA_DIR / "crawler_state.db"
MANIFESTS_DIR = DATA_DIR / "manifests"
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

WRANGLER_JS = r"C:\Users\Hieu Maico\AppData\Roaming\npm\node_modules\wrangler\bin\wrangler.js"
TOML_PATH = Path(r"C:\Users\Hieu Maico\AppData\Roaming\xdg.config\.wrangler\config\default.toml")

ACCOUNT_ID = "f486ca0e5773032c7bf96c231489a0ea"
DATABASE_ID = "1277b081-4c8b-41b4-b4c7-0007a4759c07"  # khai-phong-lms-staging
TARGET_R2_BUCKET = "khai-phong-lms-staging-files"
ADMIN_USER_ID = "0a06cb29-9889-4419-9d86-cb09b07df18e"
STORAGE_PREFIX = "documents/v1/"

logger = logging.getLogger("BeekipAPIDeployer")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


def create_session() -> requests.Session:
    """Tạo requests session có connection pooling và retry cơ bản"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=retries)
    session.mount("https://", adapter)
    return session


GLOBAL_SESSION = create_session()


def sql_quote(val) -> str:
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''")
    return f"'{s}'"


REAL_PDF_MAP: Dict[str, Path] = {}

def get_real_pdf_map() -> Dict[str, Path]:
    global REAL_PDF_MAP
    if not REAL_PDF_MAP:
        seo_dir = DATA_DIR / "TaiLieu_Chuan_SEO_GEO"
        if seo_dir.exists():
            for p in seo_dir.rglob("*.pdf"):
                REAL_PDF_MAP[p.name] = p
    return REAL_PDF_MAP


def upload_pdf_to_r2(session: requests.Session, pdf_path: Path, obj_key: str, max_retries: int = 3):
    try:
        upload_document_asset(obj_key, pdf_path.read_bytes(), "application/pdf")
        return True, ""
    except Exception as exc:
        return False, type(exc).__name__ + ": " + str(exc)


def execute_d1_sql(session: requests.Session, sql_statements: List[str], max_retries: int = 3):
    """Retired publication interface; never sends direct document SQL."""
    raise RuntimeError("Direct document SQL publication is disabled; use LMS ingest")


def deploy_batch(rows: List[Dict[str, Any]], upload_workers: int = 10) -> Dict[str, Any]:
    """Upload through Worker asset creation, then request create-only LMS ingestion."""
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

    def worker_upload(item):
        r, doc_id, file_uuid, obj_key = item
        pdf_path = Path(r["pdf_path"])
        ok, msg = upload_pdf_to_r2(GLOBAL_SESSION, pdf_path, obj_key)
        return item, ok, msg

    uploaded_items = []
    sql_statements = []
    now_ms = int(time.time() * 1000)

    with ThreadPoolExecutor(max_workers=upload_workers) as executor:
        futures = [executor.submit(worker_upload, it) for it in valid_items]
        for f in as_completed(futures):
            item, ok, msg = f.result()
            r, doc_id, file_uuid, obj_key = item
            slug = r["slug"]
            post_id = r.get("post_id", 0)

            if not ok:
                logger.error(f"Lỗi tải lên R2 [{slug}]: {msg}")
                continue

            try:
                ingest_document(r["_ingest_payload"])
            except Exception as exc:
                logger.error("LMS ingest failed for %s: %s", slug, type(exc).__name__)
                return {"uploaded": uploaded_items, "error": "LMS ingest rejected a document; see the source validation report"}
            uploaded_items.append((slug, post_id))

    return {"uploaded": uploaded_items, "error": ""}


def deploy_manifest(manifest_path: Path, batch_size: int = 25, upload_workers: int = 10, limit: Optional[int] = None):
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
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
    if limit:
        pending = pending[:limit]

    total = len(pending)
    logger.info("=" * 70)
    logger.info("🚀 KHỞI ĐỘNG BEEKIP NATIVE REST API DEPLOYER")
    logger.info(f"Manifest: {manifest_path.name}")
    logger.info(f"Số lượng cần nạp mới: {total:,} / {len(rows):,}")
    logger.info(f"D1 Database: {DATABASE_ID} | R2 Bucket: {TARGET_R2_BUCKET}")
    logger.info(f"Workers: {upload_workers} | Batch size: {batch_size}")
    logger.info("=" * 70)

    if total == 0:
        logger.info("Tất cả tài liệu trong manifest này đã được nạp thành công!")
        return

    t0 = time.time()
    total_uploaded = 0

    for i in range(0, total, batch_size):
        chunk = pending[i:i + batch_size]
        res = deploy_batch(chunk, upload_workers=upload_workers)
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
        remaining = total - total_uploaded
        eta_minutes = remaining / speed if speed > 0 else 0
        logger.info(f"[{min(i + batch_size, total):5d}/{total}] Đã nạp thành công: {total_uploaded} | Tốc độ: {speed:.0f} bài/phút | ETA: {eta_minutes:.1f} phút")

    logger.info("=" * 70)
    logger.info(f"🎉 HOÀN TẤT NẠP TÀI LIỆU CHO MANIFEST {manifest_path.name}: {total_uploaded:,} bài")
    logger.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Beekip Native REST API Deployer")
    parser.add_argument("--manifest", type=str, default="manifest_phase1_lop12.csv", help="Tệp manifest trong data/manifests/")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số bài nạp")
    parser.add_argument("--batch-size", type=int, default=25, help="Số bài nạp mỗi lô SQL D1 (mặc định: 25)")
    parser.add_argument("--workers", type=int, default=10, help="Số worker song song R2 (mặc định: 10)")
    args = parser.parse_args()

    m_path = MANIFESTS_DIR / args.manifest if not Path(args.manifest).is_absolute() else Path(args.manifest)
    if not m_path.exists():
        logger.error(f"Không tìm thấy manifest: {m_path}")
        return

    deploy_manifest(m_path, batch_size=args.batch_size, upload_workers=args.workers, limit=args.limit)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
