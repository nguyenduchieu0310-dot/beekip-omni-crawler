from cloudflare.document_ingest import ingest_config, ingest_document, upload_document_asset
from legacy_document_ingest import payload_for_manifest_row
import os
import json
import logging
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import requests
from config import BEEKIP_API_URL, BEEKIP_API_KEY, EXPORTS_DIR

logger = logging.getLogger("BeekipAgent")

WRANGLER_BIN = str(Path(r"d:\Codex\Projects\Beekip.vn\node_modules\wrangler\bin\wrangler.js"))
TARGET_DB = "khai-phong-lms-staging"
TARGET_R2_BUCKET = "khai-phong-lms-staging-files"
ADMIN_USER_ID = "0a06cb29-9889-4419-9d86-cb09b07df18e"
STORAGE_PREFIX = "documents/v1/"

def sql_quote(val):
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''")
    return f"'{s}'"

def export_to_json(payload: Dict[str, Any]) -> str:
    """
    Xuất dữ liệu bài viết và thông tin file đã xử lý ra tệp JSON trong thư mục data/exports/
    để có thể import thủ công hoặc đồng bộ hàng loạt vào hệ thống beekip.vn.
    """
    slug = payload.get("slug", f"post-{payload.get('post_id')}")
    export_file = EXPORTS_DIR / f"{slug}.json"
    with open(export_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return str(export_file)

def deploy_to_beekip_cloud(payload: Dict[str, Any], pdf_path: Optional[str] = None) -> Tuple[bool, str]:
    """Compatibility entry point: create assets and metadata through the LMS API only."""
    ingest_config()
    slug = payload.get("slug", "")
    if not slug:
        return False, "Thiếu slug tài liệu"

    if not pdf_path or not os.path.exists(pdf_path):
        return False, f"Không tìm thấy tệp PDF: {pdf_path}"

    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        pages = len(reader.pages)
    except Exception:
        pages = 1

    size_b = os.path.getsize(pdf_path)
    preview_pages = list(range(1, min(pages, 5) + 1))
    preview_json = json.dumps(preview_pages)

    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://beekip.vn/document/{slug}"))
    file_uuid = str(uuid.uuid4())
    obj_key = f"{STORAGE_PREFIX}{doc_id}/{file_uuid}.pdf"
    row = {"slug": slug, "document_code": payload.get("document_code") or slug[:50],
           "title": payload.get("seo_title") or payload.get("original_title") or slug,
           "authorName": payload.get("author_name") or "Beekip tổng hợp và sưu tầm",
           "audienceTags": payload.get("tags") or payload.get("categories") or ["Toán học"],
           "shortDescription": payload.get("meta_description", ""), "description": payload.get("content_html", ""),
           "descriptionFormat": payload.get("description_format", "html"), "pdf_path": str(pdf_path),
           "pdf_filename": Path(pdf_path).name, "pageCount": pages}
    from cloudflare.document_ingest import source_provenance
    provenance, _ = source_provenance(payload.get("original_url", ""), payload.get("original_title", ""), row["description"],
                                     payload.get("source_site"), payload.get("post_id"), payload)
    row["provenanceJson"] = json.dumps(provenance, ensure_ascii=False)
    ingest_payload = payload_for_manifest_row(row, doc_id, obj_key)
    now_ms = int(time.time() * 1000)

    upload_document_asset(obj_key, Path(pdf_path).read_bytes(), "application/pdf")

    # The LMS validates asset pointers and compiles the complete body before publication.
    ingest_document(ingest_payload)
    return True, "https://tailieu.beekip.vn/tai-lieu/" + slug


def upload_to_beekip_api(payload: Dict[str, Any], pdf_path: Optional[str] = None, word_path: Optional[str] = None) -> bool:
    """Keep a local export, then use the versioned LMS endpoint without unsafe fallbacks."""
    export_to_json(payload)

    # The compatibility function now uses only the versioned LMS endpoints.
    if pdf_path and os.path.exists(pdf_path):
        success, msg = deploy_to_beekip_cloud(payload, pdf_path)
        if success:
            return True

    # No legacy HTTP or direct SQL fallback may bypass the versioned content contract.
    logger.warning("LMS ingest is unavailable; the source export remains pending locally")
    return False
