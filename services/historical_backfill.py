import argparse
import logging
import sys
from typing import Optional

from adapters.factory import get_adapter_for_source
from core.config import LOGS_DIR, MIN_ELIGIBLE_YEAR
from core.database import DatabaseManager
from processing.temporal_guard import TemporalYearGuard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("beekip.backfill")

def run_historical_backfill(
    source_id_filter: Optional[str] = None,
    from_year: int = MIN_ELIGIBLE_YEAR,
    max_pages_per_source: int = 40
) -> None:
    """Scan and backfill historical archives from from_year to present."""
    db = DatabaseManager()
    db.sync_sources_from_json()
    sources = db.get_active_sources()

    if source_id_filter:
        sources = [s for s in sources if s["source_id"] == source_id_filter]
        if not sources:
            logger.error("Source ID [%s] not found in monitored sources.", source_id_filter)
            return

    logger.info("Starting historical archive backfill (from year %s) across %s source(s)...", from_year, len(sources))

    total_discovered = 0
    total_enqueued = 0

    for src in sources:
        sid = src["source_id"]
        logger.info("Backfilling source [%s]...", sid)
        adapter = get_adapter_for_source(src)

        batch_to_enqueue = []
        try:
            for item in adapter.fetch_historical_archive(from_year=from_year, max_pages=max_pages_per_source):
                total_discovered += 1
                guard = TemporalYearGuard.evaluate(
                    title=item.title,
                    url=item.url,
                    published_at=item.published_at,
                    published_year=item.published_year
                )

                if guard.is_eligible:
                    batch_to_enqueue.append({
                        "url": item.url,
                        "source_id": sid,
                        "title": item.title,
                        "published_year": guard.detected_year or from_year,
                        "published_at": item.published_at,
                        "discovery_cycle_id": f"backfill_{from_year}",
                        "status": "PENDING"
                    })

                if len(batch_to_enqueue) >= 50:
                    inserted = db.enqueue_inbound_items(batch_to_enqueue)
                    total_enqueued += inserted
                    batch_to_enqueue.clear()

            if batch_to_enqueue:
                inserted = db.enqueue_inbound_items(batch_to_enqueue)
                total_enqueued += inserted

        except Exception as e:
            logger.error("Error during historical backfill for [%s]: %s", sid, e)

    logger.info(
        "Historical backfill complete! Scanned: %s items, Successfully enqueued >= %s: %s items",
        total_discovered, from_year, total_enqueued
    )

def main():
    parser = argparse.ArgumentParser(description="Beekip Historical Backfill Tool (>= 2023)")
    parser.add_argument("--source", type=str, default=None, help="Specific source_id to backfill")
    parser.add_argument("--from-year", type=int, default=MIN_ELIGIBLE_YEAR, help="Start year (default 2023)")
    parser.add_argument("--pages", type=int, default=30, help="Max archive pages per source")
    args = parser.parse_args()

    run_historical_backfill(
        source_id_filter=args.source,
        from_year=args.from_year,
        max_pages_per_source=args.pages
    )

if __name__ == "__main__":
    main()
