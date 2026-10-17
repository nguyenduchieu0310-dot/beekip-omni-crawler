"""Private staging-only live producer/consumer smoke. No request without --execute."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pypdf
import requests
from cloudflare.document_ingest import document_payload, ingest_document, source_provenance, upload_document_asset

STAGING_ORIGIN = "https://hoc-staging.beekip.vn"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-file", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--execute", action="store_true", help="Create an isolated smoke fixture in staging only")
    args = parser.parse_args()
    base = os.environ.get("DOCUMENT_INGEST_BASE_URL", os.environ.get("BEEKIP_BASE_URL", "")).rstrip("/")
    if base != STAGING_ORIGIN:
        parser.error("Set DOCUMENT_INGEST_BASE_URL or BEEKIP_BASE_URL to the exact staging origin; production is forbidden")
    if not args.execute:
        print("Dry run: no HTTP request sent. Add --execute only after the staging endpoints are ready.")
        return 0
    if not os.environ.get("DOCUMENT_INGEST_TOKEN", "").strip():
        parser.error("DOCUMENT_INGEST_TOKEN must be supplied privately through the environment")
    data = args.pdf_file.read_bytes()
    if not data.startswith(b"%PDF-"):
        parser.error("A real PDF fixture is required")
    reader = pypdf.PdfReader(args.pdf_file)
    pages = len(reader.pages)
    if not 1 <= pages <= 1500:
        parser.error("PDF page count outside the document contract")
    id_ = str(uuid.uuid4())
    slug = "staging-ingest-smoke-" + id_.replace("-", "")
    source_url = "https://example.test/beekip-staging-ingest-smoke/" + id_
    key = "documents/v1/" + id_ + "/source.pdf"
    body = '<section><h2>Kiểm thử staging</h2><p>Nội dung đầy đủ; công thức $x^2 + y^2$.</p><table><tbody><tr><td>Dòng gốc</td><td>Giữ nguyên</td></tr></tbody></table></section>'
    provenance, _ = source_provenance(source_url, "Staging ingest smoke " + id_, body, "beekip-staging-smoke", id_)
    document = {"id": id_, "code": "SMOKE-" + id_.replace("-", ""), "slug": slug,
                "title": "Staging ingest smoke " + id_, "authorName": "Beekip staging smoke",
                "audienceTags": ["Staging smoke"], "shortDescription": "Isolated staging producer/consumer fixture",
                "description": body, "descriptionFormat": "html", "sourceObjectKey": key,
                "originalFilename": "staging-smoke.pdf", "mimeType": "application/pdf", "sizeBytes": len(data),
                "pageCount": pages, "previewPages": list(range(1, min(pages, 2) + 1)), "watermarkEnabled": True,
                "downloadLimit": 3, "isPublished": True, "orderIndex": 999999999, "coverUrl": None}
    payload = document_payload(document, provenance, "needs_review", [])
    report = {"version": 1, "origin": base, "documentId": id_, "slug": slug, "sourceObjectKey": key,
              "fixturePdfSha256": hashlib.sha256(data).hexdigest(), "fixturePageCount": pages, "checks": {}, "ok": False}
    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        asset = upload_document_asset(key, data, "application/pdf")
        if asset.get("created") is not True: raise RuntimeError("New smoke asset was not created")
        report["checks"]["asset_created"] = True
        reused = upload_document_asset(key, data, "application/pdf")
        if reused.get("created") is not False: raise RuntimeError("Identical asset was not reused")
        report["checks"]["asset_reused"] = True
        try:
            upload_document_asset(key, data + b"\n% smoke conflict without replacing original bytes\n", "application/pdf")
        except RuntimeError as exc:
            if "HTTP 409" not in str(exc): raise
            report["checks"]["different_asset_bytes_rejected_409"] = True
        else:
            raise RuntimeError("Different bytes were accepted for the same asset key")
        first = ingest_document(payload)
        if first.get("created") is not True: raise RuntimeError("New smoke document was not created")
        report["checks"]["document_created"] = True
        changed = copy.deepcopy(payload)
        changed["document"]["description"] = '<p>RETRY MUST NOT OVERWRITE THE ORIGINAL ARTICLE</p>'
        repeat = ingest_document(changed)
        if repeat.get("created") is not False: raise RuntimeError("Repeated source identity was not idempotent")
        report["checks"]["repeat_created_false"] = True
        public = requests.get(base + "/api/documents/" + quote(slug, safe=""), timeout=30, allow_redirects=False)
        if public.status_code != 200: raise RuntimeError("Public staging readback failed (HTTP " + str(public.status_code) + ")")
        actual = public.json().get("document", {})
        if actual.get("description") != body or actual.get("descriptionFormat") != "html" or actual.get("pageCount") != pages:
            raise RuntimeError("Readback did not preserve the original full article and PDF metadata")
        if not actual.get("descriptionContent"):
            raise RuntimeError("Readback did not include compiled document content")
        report["checks"]["original_body_preserved_after_repeat"] = True
        report["checks"]["compiled_content_returned"] = True
        report["ok"] = True
    except Exception as exc:
        report["failure"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        save()
    print(json.dumps({"ok": True, "documentId": id_, "report": str(args.report)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
