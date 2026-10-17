"""Legacy manifest adapter for the same create-only LMS ingest contract."""
import json
import re
import sqlite3
from pathlib import Path
from cloudflare.document_ingest import document_payload, source_provenance

def source_payload_for_row(row):
    if row.get("provenanceJson"):
        provenance = json.loads(row["provenanceJson"])
        match = re.search(r"-ID(\d+)$", row.get("document_code", ""))
        if match and str(provenance.get("sourceItemId")) != match.group(1):
            raise ValueError("Source post ID does not match the document code")
        return None, provenance
    slug = row["slug"]
    candidate = Path(row.get("pdf_path", "")).parent / (slug + "_meta.json")
    if candidate.is_file():
        payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        if payload.get("slug") != slug:
            raise ValueError("Source payload slug mismatch")
    else:
        database = Path(__file__).parent / "data/crawler_state.db"
        if not database.is_file():
            raise ValueError("Original source evidence missing; regenerate a provenance manifest")
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT post_id,original_url,original_title,source_site,payload_json FROM crawled_posts WHERE slug=? LIMIT 2", (slug,)).fetchall()
        if len(rows) != 1:
            raise ValueError("Source join is missing or ambiguous")
        record = dict(rows[0])
        payload = json.loads(record["payload_json"] or "{}")
        for field in ("post_id", "original_url", "original_title", "source_site"):
            payload.setdefault(field, record[field])
    match = re.search(r"-ID(\d+)$", row.get("document_code", ""))
    if match and str(payload.get("post_id")) != match.group(1):
        raise ValueError("Source post ID does not match the document code")
    provenance, _ = source_provenance(payload.get("original_url", ""), payload.get("original_title", ""),
                                     row.get("description", ""), payload.get("source_site"), payload.get("post_id"), payload)
    return payload, provenance

def payload_for_manifest_row(row, doc_id, object_key):
    pdf = Path(row["pdf_path"])
    if pdf.suffix.lower() != ".pdf":
        raise ValueError("Only a validated PDF can be published by this document endpoint")
    with pdf.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Invalid PDF signature")
    if not 0 < pdf.stat().st_size <= 50 * 1024 * 1024:
        raise ValueError("PDF size outside the document contract")
    payload, provenance = source_payload_for_row(row)
    description = row.get("description", "")
    format_ = row.get("descriptionFormat") or (payload or {}).get("description_format")
    if not format_ and payload and payload.get("content_html") == description:
        format_ = "html"
    tags = row.get("audienceTags", [])
    tags = json.loads(tags) if isinstance(tags, str) else tags
    if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
        raise ValueError("audienceTags must be a JSON string array")
    pages = int(row["pageCount"])
    if not 1 <= pages <= 1500:
        raise ValueError("Invalid page count")
    document = {"id": doc_id, "code": row["document_code"], "slug": row["slug"], "title": row["title"],
                "authorName": row.get("authorName") or "Chưa xác minh tác giả", "audienceTags": tags,
                "shortDescription": row.get("shortDescription", ""), "description": description,
                "descriptionFormat": format_, "sourceObjectKey": object_key, "originalFilename": row.get("pdf_filename") or pdf.name,
                "mimeType": "application/pdf", "sizeBytes": pdf.stat().st_size, "pageCount": pages,
                "previewPages": list(range(1, min(pages, 5) + 1)),
                "watermarkEnabled": str(row.get("watermarkEnabled", "true")).lower() != "false",
                "downloadLimit": int(row.get("downloadLimit", 3)), "isPublished": str(row.get("isPublished", "true")).lower() == "true",
                "orderIndex": int(row.get("orderIndex", 99999)), "coverUrl": row.get("coverUrl") or None}
    offers = [{"productType": "document_online", "priceVnd": int(row.get("onlinePrice", 0)), "status": row.get("onlineStatus", "active")},
              {"productType": "document_download", "priceVnd": int(row.get("downloadPrice", 0)), "status": row.get("downloadStatus", "active")}]
    # Historical generated metadata is never certified merely because a payload exists.
    return document_payload(document, provenance, "needs_review", offers)
