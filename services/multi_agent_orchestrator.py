"""
Beekip Multi-Agentic Autonomous Orchestrator (BEEKIP-SPEC-MAH-3.0).
Coordinates the 3 specialized agents:
- Agent 1: Data & Content Processor (Ingestion, Sanitization, HD Cover, SEO/GEO/News content)
- Agent 2: QA & SEO Sentinel (Independent Critic, 4-Pillar Quality Audit, Self-Healing Tickets)
- Agent 3: Auto Publisher & Google Indexer (R2 Bucket, D1 Database, IndexNow & Sitemaps)
Operates with a self-healing feedback loop with MAX_REVISIONS = 3.
"""

import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from adapters.factory import get_adapter_for_source
from processing.file_downloader import ResilientFileDownloader
from processing.pdf_converter import DocumentPDFConverter
from processing.seo_geo_enricher import SEOGEOEnricher
from processing.temporal_guard import TemporalYearGuard, NEW_CURRICULUM_KEYWORDS
from services.agent_content_processor import ContentProcessorAgent
from services.agent_qa_sentinel import QASentinelAgent
from services.agent_auto_publisher import AutoPublisherAgent
from services.indexer_sentinel import IndexerSentinel

logger = logging.getLogger("beekip.multi_agent_orchestrator")

MAX_SELF_HEALING_REVISIONS = 3


def eligible_year(item: Dict[str, Any]) -> bool:
    """Verify publication date >= 2023."""
    evidence = dict(item)
    evidence["title"] = (item.get("title") or "").lower()
    for keyword in NEW_CURRICULUM_KEYWORDS:
        evidence["title"] = evidence["title"].replace(keyword, "")
    result = TemporalYearGuard.evaluate(
        **{k: evidence.get(k) for k in ("title", "url", "published_at", "published_year")}
    )
    return result.is_eligible


class MultiAgentPipelineOrchestrator:
    """Master Orchestrator for the 3-Agent Collaborative Fleet."""
    cloud_mode = True

    def __init__(self, db, r2_uploader, d1_deployer, max_revisions: int = MAX_SELF_HEALING_REVISIONS):
        self.db = db
        self.r2 = r2_uploader
        self.d1 = d1_deployer
        self.max_revisions = max_revisions
        self.downloader = ResilientFileDownloader()

        # Instantiate Fleet Agents
        self.agent1 = ContentProcessorAgent()
        self.agent2 = QASentinelAgent()
        self.agent3 = AutoPublisherAgent(db=db, r2_uploader=r2_uploader, d1_deployer=d1_deployer)

    def process_inbound_url(self, item: Dict[str, Any], source: Dict[str, Any]) -> Optional[bool]:
        """
        Execute full Multi-Agent processing lifecycle for a single inbound item:
        1. Temporal Guard check (>= 2023).
        2. Deduplication check against D1.
        3. Download candidate document.
        4. Agent 1: Compile Draft Package.
        5. Agent 2: Audit Draft Package (Feedback loop up to MAX_REVISIONS).
        6. Agent 3: Publish to R2/D1 and trigger real-time search indexing.
        """
        url = item["url"]
        self.db.update_inbound_status(url, "PROCESSING")
        downloaded = None

        try:
            # Step 1: Temporal Validation
            if not eligible_year(item):
                self.db.update_inbound_status(url, "SKIPPED_OLD", "No verified year >= 2023")
                return False

            # Step 2: Deduplication Check
            meta = SEOGEOEnricher.enrich(item["title"], default_subject=source.get("primary_subject", "Đa môn"))
            meta.slug = f"{meta.slug[:140]}-{hashlib.sha256(url.encode()).hexdigest()[:10]}"
            if self.d1.check_document_exists(meta.slug):
                self.db.update_inbound_status(url, "COMPLETED")
                logger.info("Document already published: %s", meta.slug)
                return True

            # Step 3: Extract candidates & Download
            adapter = get_adapter_for_source(source)
            candidates = adapter.extract_download_links(url)
            if not candidates:
                self.db.update_inbound_status(url, "SKIPPED_NO_DOCUMENT", "No supported document link")
                return None

            candidate = next((c for c in candidates if c.file_type == "PDF"), candidates[0])
            downloaded = self.downloader.download(candidate.url, preferred_name=candidate.file_name)
            if downloaded is None:
                code = self.downloader.last_failure_code or "TRANSIENT_DOWNLOAD_FAILED"
                if code in {"IMAGE_REJECTED", "UNSUPPORTED_FILE_TYPE", "INVALID_PDF", "UNAVAILABLE_DOCUMENT"}:
                    self.db.update_inbound_status(url, "SKIPPED_UNSUPPORTED_DOCUMENT", code)
                    return None
                raise RuntimeError(code)

            with tempfile.TemporaryDirectory(prefix="beekip-multi-agent-") as tmp:
                working_dir = Path(tmp)
                raw_pdf = downloaded.file_path

                # Office conversion if needed
                if downloaded.mime_type != "application/pdf":
                    if not DocumentPDFConverter.can_convert():
                        self.db.update_inbound_status(url, "NEEDS_OFFICE_CONVERTER", "No LibreOffice runtime")
                        return None
                    raw_pdf = DocumentPDFConverter.convert_docx_to_pdf(raw_pdf, working_dir)
                    if raw_pdf is None:
                        raise RuntimeError("OFFICE_CONVERSION_FAILED")

                # ==============================================================
                # AGENT 1: Data & Content Processor
                # ==============================================================
                logger.info(">>> [Node 1] AGENT 1 compiling draft for: %s", item.get("title"))
                draft_package = self.agent1.process_raw_document(
                    raw_pdf_path=raw_pdf,
                    item_meta=item,
                    source=source,
                    output_dir=working_dir,
                )

                # ==============================================================
                # AGENT 2: QA & SEO Sentinel (With Self-Healing Feedback Loop)
                # ==============================================================
                logger.info(">>> [Node 2] AGENT 2 starting independent 4-Pillar QA Audit")
                audit_report = self.agent2.audit_draft_package(draft_package)

                revision_attempt = 0
                while not audit_report.is_approved and revision_attempt < self.max_revisions:
                    revision_attempt += 1
                    logger.warning(
                        "Agent 2 issued DEFECT TICKET (Attempt %d/%d). Defects: %s. Returning to Agent 1...",
                        revision_attempt,
                        self.max_revisions,
                        audit_report.defects,
                    )
                    # Agent 1 Self-Healing Refinement
                    draft_package = self.agent1.refine_draft_package(
                        draft_package=draft_package,
                        defects=audit_report.defects,
                    )
                    # Agent 2 Re-Audit
                    audit_report = self.agent2.audit_draft_package(draft_package)

                # Verdict check
                if not audit_report.is_approved:
                    rejected_summary = "; ".join(audit_report.defects)
                    logger.error("Document failed all QA revision attempts: %s", rejected_summary)
                    self.db.update_inbound_status(url, "QA_REJECTED", rejected_summary[:255])
                    return None

                logger.info(">>> [Node 2] AGENT 2 approved document! Grade: %.1f/100 (AUDIT_PASSED)", audit_report.overall_score)

                # ==============================================================
                # AGENT 3: Auto Publisher & Google Indexer
                # ==============================================================
                logger.info(">>> [Node 3] AGENT 3 deploying to Cloudflare R2 + D1 and triggering Indexing...")
                publish_res = self.agent3.publish_approved_draft(
                    draft_package=draft_package,
                    source_url=url,
                    trigger_indexing=True,
                )
                logger.info(">>> [Node 3] Publication complete: %s", publish_res["canonical_url"])
                return True

        except Exception as exc:
            code = str(exc) if isinstance(exc, RuntimeError) and str(exc).isupper() else type(exc).__name__
            logger.error("Multi-Agent document processing failed [%s]: %s", url, code)
            self.db.update_inbound_status(url, "FAILED", code, increment_retry=True)
            return False
        finally:
            if downloaded:
                downloaded.file_path.unlink(missing_ok=True)
