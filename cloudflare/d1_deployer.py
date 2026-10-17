import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
import requests
from cloudflare.document_ingest import assert_no_document_sql, document_payload, ingest_document, ingest_config, source_provenance

from core.config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_D1_DATABASE_ID,
    get_cloudflare_token,
)
from processing.seo_geo_enricher import EnrichedMetadata

logger = logging.getLogger("beekip.cloudflare.d1")

DEFAULT_ADMIN_ID = "0a06cb29-9889-4419-9d86-cb09b07df18e"

class CloudflareD1Deployer:
    """
    Publishes documents through LMS ingest; direct D1 remains for crawler ledger operations.
    Fully compatible with Beekip LMS production schema.
    """

    def __init__(
        self,
        account_id: str = CLOUDFLARE_ACCOUNT_ID,
        database_id: str = CLOUDFLARE_D1_DATABASE_ID,
        api_token: Optional[str] = None
    ):
        self.account_id = account_id
        self.database_id = database_id
        self.api_token = api_token or get_cloudflare_token()
        self.endpoint_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/"
            f"d1/database/{self.database_id}/query"
        )
        self._table_columns: Optional[set] = None

    def execute_raw_sql(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Execute parameterized SQL on D1."""
        assert_no_document_sql(sql)
        if not self.api_token:
            raise RuntimeError("Cloudflare API token not found for D1 execution.")

        payload = {"sql": sql}
        if params is not None:
            payload["params"] = params

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "wrangler/3.114.0",
        }

        resp = requests.post(self.endpoint_url, json=payload, headers=headers, timeout=25)
        if resp.status_code != 200:
            logger.error("D1 Execution error HTTP %s: %s", resp.status_code, resp.text[:200])
            raise RuntimeError(f"D1 execute error: HTTP {resp.status_code} - {resp.text[:200]}")

        data = resp.json()
        if not data.get("success", False):
            errors = data.get("errors", [])
            logger.error("D1 SQL Error: %s", errors)
            raise RuntimeError(f"D1 SQL error: {errors}")

        if not data.get('result') or any(not r.get('success', False) for r in data['result']):
            raise RuntimeError('D1 returned an unsuccessful statement result')
        return data

    def _get_columns(self) -> set:
        if self._table_columns is None:
            try:
                res = self.execute_raw_sql("PRAGMA table_info(documents);")
                results = res.get("result", [{}])[0].get("results", {})
                if isinstance(results, dict):
                    rows = results.get("rows", [])
                    self._table_columns = {r[1] for r in rows if len(r) > 1}
                elif isinstance(results, list):
                    self._table_columns = {r.get("name") for r in results if isinstance(r, dict)}
                else:
                    self._table_columns = set()
            except Exception:
                raise RuntimeError("Could not verify D1 documents schema") from None
        return self._table_columns

    def ensure_document_ingest(self):
        """Fail before asset uploads if the new publication boundary is not configured."""
        return ingest_config()

    def insert_document(
        self,
        meta: EnrichedMetadata,
        file_url: str,
        file_size_bytes: int,
        source_url: str,
        mime_type: str = "application/pdf",
        page_count: int = 1,
        cover_url: str = "",
        author_name: str = "",
        storage_key: Optional[str] = None
    ) -> str:
        """
        Insert document record into live Beekip D1 database.
        Returns the generated document UUID.
        """
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source_url))
        from urllib.parse import urlparse
        source_object_key = storage_key or urlparse(file_url).path.lstrip('/')
        tags = [meta.subject, meta.grade, meta.academic_year, meta.curriculum, meta.document_type]
        tags.extend(value for value in [meta.geo_province, meta.geo_school] if value)
        description_format = getattr(meta, "description_format", "plain")
        provenance, review = source_provenance(source_url, meta.title, meta.description)
        document = {
            "id": doc_id, "code": "crawl-" + doc_id, "slug": meta.slug, "title": meta.title,
            "authorName": author_name or meta.geo_school or "Chưa xác minh tác giả",
            "audienceTags": tags, "shortDescription": getattr(meta, "short_description", meta.description[:500]),
            "description": meta.description, "descriptionFormat": description_format,
            "sourceObjectKey": source_object_key, "originalFilename": meta.slug + ".pdf", "mimeType": mime_type,
            "sizeBytes": file_size_bytes, "pageCount": page_count,
            "previewPages": list(range(1, min(page_count, 5) + 1)), "watermarkEnabled": True,
            "downloadLimit": 3, "isPublished": True, "orderIndex": 99999, "coverUrl": cover_url or None,
        }
        ingest_document(document_payload(document, provenance, review))
        logger.info("Document acknowledged by the create-only LMS ingest endpoint: %s", doc_id)
        return doc_id

    def find_existing_document(self, source_url: str, slug: str):
        """Read identity before any asset write, including retries with a changed title/slug."""
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source_url))
        prefix = "documents/v1/" + doc_id + "/"
        result = self.execute_raw_sql(
            "SELECT id,slug,source_object_key FROM documents WHERE id=? OR source_object_key LIKE ? OR slug=? LIMIT 2",
            [doc_id, prefix + "%", slug])
        rows = result["result"][0]["results"]
        matches = [row for row in rows if row["id"] == doc_id or str(row.get("source_object_key", "")).startswith(prefix)]
        if len(matches) == 1:
            return matches[0]
        if matches or rows:
            raise RuntimeError("Existing document identity is ambiguous; manual review is required")
        return None

    def check_document_exists(self, slug_or_url: str, source_url: Optional[str] = None) -> bool:
        if source_url:
            return self.find_existing_document(source_url, slug_or_url) is not None
        result = self.execute_raw_sql("SELECT id FROM documents WHERE slug=? LIMIT 1", [slug_or_url])
        return bool(result["result"][0]["results"])
