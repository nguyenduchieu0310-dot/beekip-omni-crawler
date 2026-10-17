import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from adapters.base_adapter import DiscoveredItem, DownloadCandidate
from adapters.factory import get_adapter_for_source
from cloudflare.d1_deployer import CloudflareD1Deployer
from cloudflare.r2_uploader import CloudflareR2Uploader
from cloudflare.sitemap_indexer import SitemapIndexer
from core.config import BASE_DIR, MIN_ELIGIBLE_YEAR
from core.database import DatabaseManager
from processing.file_downloader import ResilientFileDownloader
from processing.seo_geo_enricher import SEOGEOEnricher
from processing.smart_watermark_engine import SmartWatermarkEngine
from processing.temporal_guard import TemporalYearGuard

logger = logging.getLogger("beekip.pipeline")

class DocumentProcessingPipeline:
    """
    End-to-end pipeline:
    URL Queue -> Download -> Deduplicate SHA-256 -> Smart Watermark -> SEO Enrich -> R2 Upload -> D1 Deploy.
    """

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        r2: Optional[CloudflareR2Uploader] = None,
        d1: Optional[CloudflareD1Deployer] = None,
        sitemap: Optional[SitemapIndexer] = None,
        downloader: Optional[ResilientFileDownloader] = None
    ):
        self.db = db or DatabaseManager()
        self.r2 = r2 or CloudflareR2Uploader()
        self.d1 = d1 or CloudflareD1Deployer()
        self.sitemap = sitemap or SitemapIndexer()
        self.downloader = downloader or ResilientFileDownloader()

    def process_inbound_url(self, queue_item: Dict[str, Any], source_info: Dict[str, Any]) -> bool:
        """
        Process a single queued item to full completion.
        """
        raise RuntimeError("Legacy document pipeline is retired; use the validated CloudPipeline ingest workflow")
        url = queue_item["url"]
        title = queue_item.get("title") or "Tài liệu học tập K-12"
        source_id = queue_item["source_id"]

        logger.info("Starting processing item [%s]: %s", source_id, url)
        self.db.update_inbound_status(url, "PROCESSING")

        try:
            # 1. Temporal Year Guard verification
            guard_res = TemporalYearGuard.evaluate(
                title=title,
                url=url,
                published_at=queue_item.get("published_at"),
                published_year=queue_item.get("published_year")
            )
            if not guard_res.is_eligible:
                logger.info("Item skipped by TemporalYearGuard: %s (%s)", url, guard_res.reason)
                self.db.update_inbound_status(url, "SKIPPED_OLD", guard_res.reason)
                return False

            # 2. Extract Download Links via Adapter
            adapter = get_adapter_for_source(source_info)
            candidates = adapter.extract_download_links(url)

            if not candidates:
                logger.warning("No candidate download files found for: %s", url)
                self.db.update_inbound_status(url, "FAILED", "NO_DOWNLOAD_CANDIDATE_FOUND", increment_retry=True)
                return False

            # Prioritize PDF candidates
            primary_candidate = next((c for c in candidates if c.file_type == "PDF"), candidates[0])

            # 3. Download file
            download_res = self.downloader.download(primary_candidate.url, preferred_name=primary_candidate.file_name)
            if not download_res or not download_res.file_path.is_file():
                logger.warning("File download failed for: %s", primary_candidate.url)
                self.db.update_inbound_status(url, "FAILED", "DOWNLOAD_ERROR", increment_retry=True)
                return False

            file_size = download_res.file_size_bytes
            sha256 = download_res.sha256_hash

            # 4. SEO & GEO Enrichment
            primary_subject = source_info.get("primary_subject", "Toán")
            meta = SEOGEOEnricher.enrich(title, default_subject=primary_subject)
            if guard_res.curriculum and meta.curriculum == "GDPT 2018":
                meta.curriculum = guard_res.curriculum

            # 5. Deduplication check against file_blobs
            existing_blob = self.db.get_blob_by_hash(sha256)
            if existing_blob:
                logger.info("File blob duplicate detected (%s). Reusing storage.", sha256[:10])
                public_file_url = existing_blob["public_file_url"]
                r2_key = existing_blob["r2_storage_key"]
            else:
                # 6. Apply Smart Watermark & Layout Cleaning (if PDF)
                processed_bytes = download_res.file_path.read_bytes()
                if download_res.mime_type == "application/pdf":
                    try:
                        processed_bytes = SmartWatermarkEngine.clean_and_brand_pdf(
                            processed_bytes,
                            apply_cleanup=True,
                            apply_beekip_branding=True
                        )
                    except Exception as e:
                        logger.warning("Watermark engine warning on %s: %s", url, e)

                # 7. Upload to Cloudflare R2
                subject_slug = SEOGEOEnricher.generate_slug(meta.subject)
                r2_key, public_file_url = self.r2.upload_document(
                    file_input=processed_bytes,
                    subject_slug=subject_slug,
                    academic_year=meta.academic_year,
                    document_slug=meta.slug,
                    mime_type=download_res.mime_type
                )
                self.db.record_file_blob(
                    sha256_hash=sha256,
                    file_size_bytes=len(processed_bytes),
                    r2_storage_key=r2_key,
                    public_file_url=public_file_url,
                    first_seen_url=url
                )

            # 8. Deploy to Cloudflare D1
            doc_id = self.d1.insert_document(
                meta=meta,
                file_url=public_file_url,
                file_size_bytes=file_size,
                source_url=url,
                mime_type=download_res.mime_type
            )

            # 9. Update Sitemap & Mark COMPLETED
            self.sitemap.add_document_url(meta.slug)
            self.db.update_inbound_status(url, "COMPLETED")

            # Clean up local raw download
            try:
                download_res.file_path.unlink(missing_ok=True)
            except Exception:
                pass

            logger.info("Successfully processed and deployed document [%s] -> %s", doc_id, meta.slug)
            return True

        except Exception as e:
            logger.error("Exception during document pipeline [%s]: %s", url, e, exc_info=True)
            self.db.update_inbound_status(url, "FAILED", str(e)[:250], increment_retry=True)
            return False
