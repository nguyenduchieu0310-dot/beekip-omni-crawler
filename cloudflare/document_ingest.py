"""Create-only LMS publication; crawler ledger D1 access stays separate.

Never imports runtime config, downloads assets, runs SQL, or opens a browser.
"""
import hashlib
import json
import os
import re
from urllib.parse import urlsplit, urlunsplit
import requests

CONTRACT_VERSION = 1
MAX_DESCRIPTION_CHARS = 12_000

def ingest_config():
    token = os.environ.get("DOCUMENT_INGEST_TOKEN", "").strip()
    base = os.environ.get("DOCUMENT_INGEST_BASE_URL", os.environ.get("BEEKIP_BASE_URL", "https://tailieu.beekip.vn")).strip().rstrip("/")
    url = urlsplit(base)
    if not token:
        raise RuntimeError("DOCUMENT_INGEST_TOKEN is required; direct document D1 publication is disabled")
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise RuntimeError("DOCUMENT_INGEST_BASE_URL must be an HTTPS origin")
    return base + "/api/internal/documents/ingest", token

def source_provenance(source_url, original_title, description, source_site=None, source_item_id=None, payload=None):
    parsed = urlsplit(source_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("An unambiguous canonical original source URL is required")
    evidence = []
    review = "needs_review"
    try:
        from geo_entity_extractor import extract_geo_and_metadata
        geo = extract_geo_and_metadata(original_title)
        evidence = geo.get("geo_evidence", [])
        review = geo.get("metadata_review_status", "needs_review")
    except ImportError:
        pass
    snapshot = payload if payload is not None else {"originalUrl": source_url, "originalTitle": original_title, "description": description}
    digest = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"sourceSite": source_site or parsed.hostname, "sourceItemId": str(source_item_id) if source_item_id is not None else None,
            "originalUrl": source_url, "originalTitle": original_title, "sourcePayloadSha256": digest,
            "importerVersion": "beekip-document-ingest-v1", "metadataEvidence": evidence,
            "ruleVersion": "province-full-alias-v1"}, review

def document_payload(document, provenance, metadata_review="needs_review", offers=None):
    source = urlsplit(provenance.get("originalUrl", ""))
    if source.scheme not in ("http", "https") or not source.hostname or source.username or source.password or source.fragment:
        raise ValueError("An unambiguous original source URL is required")
    if not isinstance(provenance.get("originalTitle"), str) or not provenance["originalTitle"].strip():
        raise ValueError("The original source title is required")
    if not re.fullmatch(r"[0-9a-f]{64}", provenance.get("sourcePayloadSha256", "")):
        raise ValueError("A source payload SHA-256 is required")
    if document.get("descriptionFormat") not in ("plain", "markdown", "html"):
        raise ValueError("descriptionFormat must be explicit")
    for field, limit in [("title", 200), ("shortDescription", 500), ("description", MAX_DESCRIPTION_CHARS)]:
        value = document.get(field, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(field + " exceeds its contract limit; content must not be truncated")
    if not document.get("sourceObjectKey", "").startswith("documents/v1/" + document["id"] + "/"):
        raise ValueError("sourceObjectKey must belong to the document")
    return {"schemaVersion": CONTRACT_VERSION, "document": document, "provenance": provenance,
            "quality": {"validatorVersion": "crawler-contract-v1", "metadataReviewStatus": metadata_review,
                        "issueCodes": [] if metadata_review == "verified" else ["METADATA_REVIEW_REQUIRED"], "renderStatus": "pending"},
            "offers": offers if offers is not None else []}

def ingest_document(payload, session=None):
    endpoint, token = ingest_config()
    # Revalidate locally even when callers construct payload dictionaries directly.
    document_payload(payload["document"], payload["provenance"], payload.get("quality", {}).get("metadataReviewStatus", "needs_review"), payload.get("offers"))
    transport = session or requests
    response = transport.post(endpoint, json=payload, headers={"Authorization": "Bearer " + token,
                              "Content-Type": "application/json"}, timeout=30, allow_redirects=False)
    if response.status_code not in (200, 201):
        raise RuntimeError("LMS document ingest rejected publication (HTTP " + str(response.status_code) + ")")
    result = response.json()
    if result.get("ok") is not True or result.get("id") != payload["document"]["id"]:
        raise RuntimeError("LMS document ingest returned an invalid acknowledgement")
    return result

def assert_no_document_sql(sql):
    # Strip comments and literals before examining table names; ledger payloads can mention documents.
    scrubbed = re.sub(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'", " ", sql, flags=re.S)
    if re.search(r"\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP)\b[\s\S]*?\b(?:documents|product_offers)\b", scrubbed, re.I):
        raise RuntimeError("Direct document SQL publication is disabled; use LMS document ingest")


def upload_document_asset(key, content, mime_type, session=None):
    """Only the Worker R2 binding may create canonical document assets atomically."""
    from urllib.parse import quote
    endpoint, token = ingest_config()
    if not re.fullmatch(r"documents/v1/[a-fA-F0-9-]{36}/(?:source\.pdf|cover\.(?:jpg|png|webp)|[a-fA-F0-9-]{36}\.pdf)", key):
        raise ValueError("Unsupported document asset key")
    limits = {"application/pdf": 50 * 1024 * 1024, "image/jpeg": 2 * 1024 * 1024,
              "image/png": 2 * 1024 * 1024, "image/webp": 2 * 1024 * 1024}
    if mime_type not in limits or not 0 < len(content) <= limits[mime_type]:
        raise ValueError("Document asset MIME or size is outside the contract")
    digest = hashlib.sha256(content).hexdigest()
    transport = session or requests
    response = transport.post(endpoint.removesuffix("/ingest") + "/assets?key=" + quote(key, safe=""),
                              data=content, headers={"Authorization": "Bearer " + token, "Content-Type": mime_type,
                              "X-Content-Sha256": digest}, timeout=60, allow_redirects=False)
    if response.status_code not in (200, 201):
        raise RuntimeError("LMS document asset rejected upload (HTTP " + str(response.status_code) + ")")
    result = response.json()
    if result.get("ok") is not True or result.get("key") != key or result.get("size") != len(content) or result.get("sha256") != digest:
        raise RuntimeError("LMS document asset returned an invalid acknowledgement")
    return result
