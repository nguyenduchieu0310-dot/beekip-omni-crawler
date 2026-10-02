import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
import requests

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
    Inserts processed document metadata directly into Cloudflare D1 documents table.
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
        cols = self._get_columns()
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source_url))
        now_ms = int(time.time() * 1000)

        # Check if table uses production Beekip LMS schema
        if "audience_tags_json" in cols:
            tags = [meta.subject, meta.grade, meta.academic_year, meta.curriculum, meta.document_type]
            if meta.geo_province:
                tags.append(meta.geo_province)
            if meta.geo_school:
                tags.append(meta.geo_school)

            audience_tags_json = json.dumps(tags, ensure_ascii=False)
            from urllib.parse import urlparse
            source_object_key = storage_key or urlparse(file_url).path.lstrip('/')
            orig_filename = f"{meta.slug}.pdf"
            preview_json = json.dumps(list(range(1, min(page_count, 5) + 1)))

            sql = """
            INSERT INTO documents (
                id, document_code, slug, title, author_name, audience_tags_json,
                short_description, description, source_object_key, original_filename,
                mime_type, size_bytes, page_count, preview_pages_json, watermark_enabled,
                download_limit, is_published, order_index, created_by, updated_by,
                created_at, updated_at, cover_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING;
            """
            params = [
                doc_id,
                'crawl-' + doc_id,
                meta.slug,
                meta.title[:200],
                author_name or meta.geo_school or "Chưa xác minh tác giả",
                audience_tags_json,
                meta.description[:500],
                meta.description,
                source_object_key,
                orig_filename,
                mime_type,
                file_size_bytes,
                page_count,
                preview_json,
                1,
                3,
                1,
                99999,
                DEFAULT_ADMIN_ID,
                DEFAULT_ADMIN_ID,
                now_ms,
                now_ms,
                cover_url
            ]
        else:
            # Fallback to Spec Section 7.2 schema
            sql = """
            INSERT INTO documents (
                id, title, slug, description, subject, grade, academic_year,
                geo_province, geo_school, curriculum, document_type,
                file_url, mime_type, file_size, source_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO NOTHING;
            """
            params = [
                doc_id,
                meta.title,
                meta.slug,
                meta.description,
                meta.subject,
                meta.grade,
                meta.academic_year,
                meta.geo_province,
                meta.geo_school,
                meta.curriculum,
                meta.document_type,
                file_url,
                mime_type,
                file_size_bytes,
                source_url
            ]

        self.execute_raw_sql(sql, params)
        logger.info("Successfully deployed document to D1: [%s] (%s)", doc_id, meta.title[:50])
        return doc_id

    def check_document_exists(self, slug_or_url: str) -> bool:
        """Check if document already exists in D1."""
        sql = "SELECT count(1) as count FROM documents WHERE slug = ?;"
        try:
            res = self.execute_raw_sql(sql, [slug_or_url])
            rows = res['result'][0]['results']
            if rows and rows[0]['count'] > 0:
                return True
        except Exception:
            raise RuntimeError('Could not check D1 document existence') from None
        return False
