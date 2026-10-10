"""
Agent 3: Auto Publisher & Google Indexer Agent (Beekip Multi-Agentic Architecture).
Responsibilities:
- Receives certified drafts (AUDIT_PASSED) from Agent 2.
- Deploys PDF and Cover assets to Cloudflare R2 Storage.
- Persists verified document metadata into Cloudflare D1 Database.
- Dispatches instant indexing signals (IndexNow API + Google Sitemaps ping).
- Updates queue ledger status to COMPLETED.
"""

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from core.config import BEEKIP_BASE_URL
from processing.seo_geo_enricher import SEOGEOEnricher
from services.indexer_sentinel import IndexerSentinel

logger = logging.getLogger("beekip.agent3_publisher")


class AutoPublisherAgent:
    """Agent 3: Automated Cloud Deployment & Instant Indexing."""

    def __init__(self, db, r2_uploader, d1_deployer, indexer: Optional[IndexerSentinel] = None):
        self.db = db
        self.r2 = r2_uploader
        self.d1 = d1_deployer
        self.indexer = indexer or IndexerSentinel()

    def publish_approved_draft(
        self,
        draft_package: Dict[str, Any],
        source_url: str,
        trigger_indexing: bool = True,
    ) -> Dict[str, Any]:
        """
        Deploy document to Cloudflare R2 + D1 and trigger real-time search engine indexing.
        """
        clean_pdf_path = Path(draft_package["clean_pdf_path"])
        cover_image_path = Path(draft_package["cover_image_path"])

        if not clean_pdf_path.is_file() or not cover_image_path.is_file():
            raise FileNotFoundError("Draft payload files missing for publication.")

        payload_bytes = clean_pdf_path.read_bytes()
        cover_bytes = cover_image_path.read_bytes()

        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source_url))
        slug = draft_package["slug"]
        subject_slug = SEOGEOEnricher.generate_slug(draft_package.get("subject", "toan"))
        academic_year = str(draft_package.get("academic_year", "2026"))

        # 1. Upload PDF and Cover to Cloudflare R2
        pdf_storage_key = f"documents/v1/{doc_id}/source.pdf"
        cover_storage_key = f"documents/v1/{doc_id}/cover.jpg"

        r2_pdf_key, _ = self.r2.upload_document(
            payload_bytes,
            subject_slug,
            academic_year,
            slug,
            mime_type="application/pdf",
            ext="pdf",
            storage_key=pdf_storage_key,
        )

        r2_cover_key, _ = self.r2.upload_document(
            cover_bytes,
            subject_slug,
            academic_year,
            slug,
            mime_type="image/jpeg",
            ext="jpg",
            storage_key=cover_storage_key,
        )

        # 2. Public Route Construction
        base_route = f"{BEEKIP_BASE_URL.rstrip('/')}/api/documents/{quote(slug, safe='')}"
        file_url = f"{base_route}/download"
        cover_url = f"{base_route}/cover"
        canonical_page_url = f"{BEEKIP_BASE_URL.rstrip('/')}/tai-lieu/{quote(slug, safe='')}"

        # 3. Record blobs in ledger
        for blob_bytes, obj_key, p_url in (
            (payload_bytes, r2_pdf_key, file_url),
            (cover_bytes, r2_cover_key, cover_url),
        ):
            self.db.record_file_blob(
                hashlib.sha256(blob_bytes).hexdigest(),
                len(blob_bytes),
                obj_key,
                p_url,
                source_url,
            )

        # 4. Insert into Cloudflare D1
        meta_enricher_obj = SEOGEOEnricher.enrich(draft_package["title"])
        meta_enricher_obj.slug = slug
        meta_enricher_obj.description = draft_package["description"]
        meta_enricher_obj.subject = draft_package.get("subject", meta_enricher_obj.subject)
        meta_enricher_obj.grade = draft_package.get("grade", meta_enricher_obj.grade)
        meta_enricher_obj.document_type = draft_package.get("category", meta_enricher_obj.document_type)

        self.d1.insert_document(
            meta_enricher_obj,
            file_url,
            len(payload_bytes),
            source_url,
            page_count=draft_package.get("page_count", 1),
            cover_url=cover_url,
            author_name=draft_package.get("author_name", "Beekip"),
            storage_key=r2_pdf_key,
        )

        # 5. Mark D1 Queue as COMPLETED
        self.db.update_inbound_status(source_url, "COMPLETED")

        # 6. Trigger Real-time Indexing
        indexing_results = {}
        if trigger_indexing:
            indexing_results["indexnow"] = self.indexer.notify_indexnow([canonical_page_url])
            indexing_results["sitemap_ping"] = self.indexer.ping_sitemaps()

        publish_result = {
            "success": True,
            "document_id": doc_id,
            "title": draft_package["title"],
            "slug": slug,
            "canonical_url": canonical_page_url,
            "file_url": file_url,
            "cover_url": cover_url,
            "pdf_key": r2_pdf_key,
            "cover_key": r2_cover_key,
            "size_bytes": len(payload_bytes),
            "indexing": indexing_results,
        }

        logger.info(
            "Agent 3 successfully published document [%s] -> %s (Indexed via IndexNow: %s)",
            doc_id,
            canonical_page_url,
            indexing_results.get("indexnow", {}).get("success", False),
        )
        return publish_result
