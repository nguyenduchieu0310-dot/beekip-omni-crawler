import argparse
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from adapters.factory import get_adapter_for_source
from core.config import (
    LOGS_DIR,
    MAX_WORKER_THREADS,
    MONITOR_INTERVAL_HOURS,
    SCHEDULED_RUN_HOURS,
)
from core.database import DatabaseManager
from core.worker_pool import DomainBoundWorkerPool
from processing.temporal_guard import TemporalYearGuard
from services.pipeline import DocumentProcessingPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "omni_scheduler.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("beekip.scheduler")

class OmniSchedulerDaemon:
    """
    Automated 4-Hour Continuous Monitoring Daemon for 20+ K-12 educational sources.
    Executes conditional delta scans, filters >= 2023, and runs parallel worker pool.
    """

    def __init__(self, db: Optional[DatabaseManager] = None, pipeline=None):
        self.db = db or DatabaseManager()
        self.db.sync_sources_from_json()
        self.pipeline = pipeline or DocumentProcessingPipeline(db=self.db)
        self.worker_pool = DomainBoundWorkerPool(max_workers=MAX_WORKER_THREADS)

    def run_single_cycle(self, max_items_per_cycle: int = 50, scan_budget_seconds=None) -> Dict[str, Any]:
        """
        Execute a complete 4-hour monitoring cycle:
        1. Differential scan of all active sources.
        2. Enqueue new articles matching >= 2023.
        3. Dispatch to worker pool for downloading, cleaning, and deployment.
        """
        cycle_id = f"cycle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        start_time = time.perf_counter()

        logger.info(">>> Starting Omni-Agent Monitoring Cycle [%s] <<<", cycle_id)
        self.db.create_monitoring_cycle(cycle_id)

        sources = self.db.get_active_sources()
        sources_checked = 0
        new_urls_found = 0
        urls_accepted_2023 = 0
        urls_rejected_old = 0
        source_errors = 0

        # Step 1: Scan all sources with conditional headers (< 90-180 seconds SLA)
        for src in sources:
            if scan_budget_seconds is not None and time.perf_counter() - start_time >= scan_budget_seconds:
                break
            source_id = src["source_id"]
            etag = src.get("last_etag")
            last_mod = src.get("last_modified_header")

            try:
                adapter = get_adapter_for_source(src)
                responses = []
                if getattr(self.pipeline, 'cloud_mode', False) and hasattr(adapter, 'session'):
                    original_request = adapter.session.request
                    def observed_request(*args, _request=original_request, **kwargs):
                        response = _request(*args, **kwargs)
                        responses.append(response.status_code)
                        return response
                    adapter.session.request = observed_request
                latest_items = adapter.fetch_latest_posts(etag=etag, last_modified=last_mod)
                if getattr(self.pipeline, 'cloud_mode', False) and not latest_items and not any(code in (200, 304) for code in responses):
                    raise RuntimeError('SOURCE_UNAVAILABLE')
                sources_checked += 1

                # Persist cache headers only after every discovered URL is durable.
                new_etag = adapter.source_info.get("_last_etag")
                new_last_mod = adapter.source_info.get("_last_modified")
                items_to_enqueue = []
                for item in latest_items:
                    new_urls_found += 1
                    guard = TemporalYearGuard.evaluate(
                        title=item.title,
                        url=item.url,
                        published_at=item.published_at,
                        published_year=item.published_year
                    )
                    if getattr(self.pipeline, 'cloud_mode', False):
                        from services.cloud_pipeline import eligible_year
                        if not eligible_year(vars(item)):
                            guard.is_eligible = False
                            guard.reason = 'NO_VERIFIED_YEAR_GE_2023'

                    if guard.is_eligible:
                        urls_accepted_2023 += 1
                        items_to_enqueue.append({
                            "url": item.url,
                            "source_id": source_id,
                            "title": item.title,
                            "published_year": guard.detected_year or 2024,
                            "published_at": item.published_at,
                            "discovery_cycle_id": cycle_id,
                            "status": "PENDING",
                            "error_message": None
                        })
                    else:
                        urls_rejected_old += 1
                        items_to_enqueue.append({
                            "url": item.url,
                            "source_id": source_id,
                            "title": item.title,
                            "published_year": guard.detected_year or (item.published_year or 2022),
                            "published_at": item.published_at,
                            "discovery_cycle_id": cycle_id,
                            "status": "SKIPPED_OLD",
                            "error_message": guard.reason
                        })

                if items_to_enqueue:
                    self.db.enqueue_inbound_items(items_to_enqueue)
                self.db.update_source_sync_meta(source_id, etag=new_etag, last_modified=new_last_mod)

            except Exception as e:
                source_errors += 1
                if getattr(self.pipeline, 'cloud_mode', False):
                    self.db.update_source_sync_meta(source_id)
                logger.error("Error checking source [%s]: %s", source_id, e)

        # Step 2: Dispatch pending items in inbound_queue to Worker Pool
        pending_items = self.db.get_pending_inbound_items(limit=max_items_per_cycle)
        logger.info("Dispatching %s items from inbound queue to Worker Pool...", len(pending_items))

        source_lookup = {s["source_id"]: s for s in sources}
        futures = []
        for q_item in pending_items:
            src_info = source_lookup.get(q_item["source_id"], {"domain": "unknown", "primary_subject": "Đa môn"})
            domain = src_info.get("domain", "unknown")
            f = self.worker_pool.submit(domain, self.pipeline.process_inbound_url, q_item, src_info)
            futures.append(f)

        deployed_count = 0
        failed_count = 0
        for f in futures:
            try:
                if f.result(timeout=120):
                    deployed_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.error("Worker processing failed: %s", e)

        duration = time.perf_counter() - start_time
        logger.info(
            ">>> Completed Cycle [%s] in %.2fs: Sources: %s, Found: %s, Accepted: %s, Rejected: %s, Deployed: %s <<<",
            cycle_id, duration, sources_checked, new_urls_found, urls_accepted_2023, urls_rejected_old, deployed_count
        )

        self.db.complete_monitoring_cycle(
            cycle_id=cycle_id,
            sources_checked=sources_checked,
            new_urls_found=new_urls_found,
            urls_accepted=urls_accepted_2023,
            urls_rejected=urls_rejected_old,
            deployed_count=deployed_count,
            duration_seconds=duration,
            status="FAILED" if source_errors or failed_count or not sources_checked else "SUCCESS"
        )

        # Ping search engines if any documents were deployed
        if deployed_count > 0 and not getattr(self.pipeline, 'cloud_mode', False):
            self.pipeline.sitemap.ping_search_engines()

        return {
            "cycle_id": cycle_id,
            "duration": duration,
            "sources_checked": sources_checked,
            "new_urls_found": new_urls_found,
            "urls_accepted_2023": urls_accepted_2023,
            "urls_rejected_old": urls_rejected_old,
            "deployed_count": deployed_count,
            "failed_count": failed_count,
            "source_errors": source_errors,
            "deferred_sources": len(sources) - sources_checked - source_errors,
        }

    def start_247_daemon(self) -> None:
        """Run continuous 24/7 loop triggering on scheduled hours."""
        logger.info("Beekip Omni-Agent Daemon started 24/7. Target hours (UTC+7): %s", SCHEDULED_RUN_HOURS)

        # Run an initial cycle upon startup
        self.run_single_cycle()

        while True:
            now = datetime.now()
            # Calculate sleep until next 4h milestone
            current_hour = now.hour
            # Find next target hour in SCHEDULED_RUN_HOURS
            next_hours = [h for h in SCHEDULED_RUN_HOURS if h > current_hour]
            next_target = next_hours[0] if next_hours else SCHEDULED_RUN_HOURS[0]

            # Sleep in 60s intervals to stay responsive
            time.sleep(60)
            now = datetime.now()
            if now.hour in SCHEDULED_RUN_HOURS and now.minute == 0:
                logger.info("Scheduled 4-hour trigger hit: %s:00", now.hour)
                self.run_single_cycle()
                time.sleep(120)  # Avoid duplicate trigger in same minute

def main():
    parser = argparse.ArgumentParser(description="Beekip Omni-Agent 4-Hour Monitor & Sync Engine")
    parser.add_argument("--run-now", action="store_true", help="Run a single monitoring cycle immediately and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in 24/7 background mode")
    parser.add_argument("--limit", type=int, default=50, help="Max items to process in cycle")
    args = parser.parse_args()

    daemon = OmniSchedulerDaemon()

    if args.run_now:
        daemon.run_single_cycle(max_items_per_cycle=args.limit)
    else:
        daemon.start_247_daemon()

if __name__ == "__main__":
    main()
