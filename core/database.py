import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import DB_PATH, SOURCES_REGISTRY_PATH

logger = logging.getLogger("beekip.database")

SCHEMA_SQL = """
-- 1. Monitored Sources Catalog
CREATE TABLE IF NOT EXISTS monitored_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    tier INTEGER NOT NULL,
    primary_subject TEXT NOT NULL,
    protocol TEXT NOT NULL,
    feed_url TEXT NOT NULL,
    check_interval_minutes INTEGER DEFAULT 240,
    last_synced_at TEXT,
    last_etag TEXT,
    last_modified_header TEXT,
    status TEXT DEFAULT 'ACTIVE',
    concurrency_limit INTEGER DEFAULT 2,
    rate_delay_seconds REAL DEFAULT 2.5
);

-- 2. Inbound Document Queue
CREATE TABLE IF NOT EXISTS inbound_queue (
    url TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT,
    published_year INTEGER,
    published_at TEXT,
    discovery_cycle_id TEXT,
    status TEXT DEFAULT 'PENDING',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(source_id) REFERENCES monitored_sources(source_id)
);

CREATE INDEX IF NOT EXISTS idx_inbound_status ON inbound_queue(status);
CREATE INDEX IF NOT EXISTS idx_inbound_source ON inbound_queue(source_id);

-- 3. Monitoring Cycles Log
CREATE TABLE IF NOT EXISTS monitoring_cycles_log (
    cycle_id TEXT PRIMARY KEY,
    triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    sources_checked INTEGER DEFAULT 0,
    new_urls_found INTEGER DEFAULT 0,
    urls_accepted_2023 INTEGER DEFAULT 0,
    urls_rejected_old INTEGER DEFAULT 0,
    deployed_to_beekip INTEGER DEFAULT 0,
    duration_seconds REAL,
    status TEXT DEFAULT 'SUCCESS'
);

-- 4. SHA-256 Deduplication & Storage Register
CREATE TABLE IF NOT EXISTS file_blobs (
    sha256_hash TEXT PRIMARY KEY,
    file_size_bytes INTEGER NOT NULL,
    r2_storage_key TEXT NOT NULL,
    public_file_url TEXT NOT NULL,
    first_seen_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

class DatabaseManager:
    """Manages SQLite state ledger for Beekip Omni-Agent."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create a new connection configured for high-concurrency WAL mode."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=15000;")
        return conn

    def _init_db(self) -> None:
        """Initialize all schema tables and indexes."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def sync_sources_from_json(self, registry_file: Path = SOURCES_REGISTRY_PATH) -> int:
        """Sync or insert source registry entries into monitored_sources table."""
        if not registry_file.is_file():
            logger.warning("Source registry file not found: %s", registry_file)
            return 0

        with open(registry_file, "r", encoding="utf-8") as f:
            registry_data = json.load(f)

        count = 0
        with self.get_connection() as conn:
            for item in registry_data:
                source_id = item.get("source_id")
                name = item.get("name", "")
                domain = item.get("domain", "")
                tier = int(item.get("tier", 3))
                primary_subject = item.get("primary_subject", "Đa môn")
                protocol = item.get("protocol", "RSS_XML")
                feed_url = item.get("feed_url") or item.get("sitemap_url") or f"https://{domain}"
                check_interval = int(item.get("check_interval_minutes", 240))
                rate_delay = float(item.get("rate_limit_delay_seconds", 2.5))
                status = item.get("status", "ACTIVE")

                conn.execute(
                    """
                    INSERT INTO monitored_sources (
                        source_id, name, domain, tier, primary_subject,
                        protocol, feed_url, check_interval_minutes,
                        rate_delay_seconds, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        name=excluded.name,
                        domain=excluded.domain,
                        tier=excluded.tier,
                        primary_subject=excluded.primary_subject,
                        protocol=excluded.protocol,
                        feed_url=excluded.feed_url,
                        check_interval_minutes=excluded.check_interval_minutes,
                        rate_delay_seconds=excluded.rate_delay_seconds,
                        status=excluded.status
                    """,
                    (
                        source_id, name, domain, tier, primary_subject,
                        protocol, feed_url, check_interval, rate_delay, status
                    )
                )
                count += 1
            conn.commit()
        return count

    def get_active_sources(self) -> List[Dict[str, Any]]:
        """Retrieve all active sources configured for monitoring."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM monitored_sources WHERE status = 'ACTIVE' ORDER BY tier ASC, source_id ASC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_source_sync_meta(
        self,
        source_id: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        last_synced_at: Optional[str] = None
    ) -> None:
        """Update last sync timestamp and HTTP conditional caching headers."""
        if last_synced_at is None:
            last_synced_at = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE monitored_sources
                SET last_etag = COALESCE(?, last_etag),
                    last_modified_header = COALESCE(?, last_modified_header),
                    last_synced_at = ?
                WHERE source_id = ?
                """,
                (etag, last_modified, last_synced_at, source_id)
            )
            conn.commit()

    def enqueue_inbound_items(self, items: List[Dict[str, Any]]) -> int:
        """Enqueue newly discovered URLs into inbound_queue idempotently."""
        if not items:
            return 0

        inserted = 0
        with self.get_connection() as conn:
            for item in items:
                cursor = conn.execute(
                    """
                    INSERT INTO inbound_queue (
                        url, source_id, title, published_year,
                        published_at, discovery_cycle_id, status, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title = excluded.title,
                        published_year = COALESCE(excluded.published_year, inbound_queue.published_year),
                        status = CASE 
                            WHEN inbound_queue.status IN ('COMPLETED', 'DOWNLOADED_LOCAL', 'NO_DOWNLOAD_LINK', 'SKIPPED_OLD', 'SKIPPED_MONITOR_ONLY') 
                            THEN inbound_queue.status 
                            ELSE excluded.status 
                        END,
                        error_message = COALESCE(inbound_queue.error_message, excluded.error_message)
                    """,
                    (
                        item.get("url"),
                        item.get("source_id"),
                        item.get("title"),
                        item.get("published_year"),
                        item.get("published_at"),
                        item.get("discovery_cycle_id"),
                        item.get("status", "PENDING"),
                        item.get("error_message")
                    )
                )
                if cursor.rowcount > 0:
                    inserted += 1
            conn.commit()
        return inserted

    def get_pending_inbound_items(self, limit: int = 50, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch pending items from queue."""
        with self.get_connection() as conn:
            if source_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM inbound_queue
                    WHERE status = 'PENDING' AND source_id = ?
                    ORDER BY created_at ASC LIMIT ?
                    """,
                    (source_id, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM inbound_queue
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC LIMIT ?
                    """,
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def update_inbound_status(
        self,
        url: str,
        status: str,
        error_message: Optional[str] = None,
        increment_retry: bool = False
    ) -> None:
        """Update processing status of an inbound URL item."""
        with self.get_connection() as conn:
            if increment_retry:
                conn.execute(
                    """
                    UPDATE inbound_queue
                    SET status = ?, error_message = ?, retry_count = retry_count + 1
                    WHERE url = ?
                    """,
                    (status, error_message, url)
                )
            else:
                conn.execute(
                    """
                    UPDATE inbound_queue
                    SET status = ?, error_message = ?
                    WHERE url = ?
                    """,
                    (status, error_message, url)
                )
            conn.commit()

    def record_file_blob(
        self,
        sha256_hash: str,
        file_size_bytes: int,
        r2_storage_key: str,
        public_file_url: str,
        first_seen_url: Optional[str] = None
    ) -> bool:
        """Register newly uploaded file blob for cross-document deduplication."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO file_blobs (
                    sha256_hash, file_size_bytes, r2_storage_key,
                    public_file_url, first_seen_url
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (sha256_hash, file_size_bytes, r2_storage_key, public_file_url, first_seen_url)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_blob_by_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        """Check if file hash already exists in file_blobs."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM file_blobs WHERE sha256_hash = ?",
                (sha256_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_monitoring_cycle(self, cycle_id: str) -> None:
        """Create new cycle record in monitoring_cycles_log."""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO monitoring_cycles_log (cycle_id, status) VALUES (?, 'RUNNING')",
                (cycle_id,)
            )
            conn.commit()

    def complete_monitoring_cycle(
        self,
        cycle_id: str,
        sources_checked: int,
        new_urls_found: int,
        urls_accepted: int,
        urls_rejected: int,
        deployed_count: int,
        duration_seconds: float,
        status: str = "SUCCESS"
    ) -> None:
        """Record final stats for a monitoring cycle."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE monitoring_cycles_log
                SET sources_checked = ?,
                    new_urls_found = ?,
                    urls_accepted_2023 = ?,
                    urls_rejected_old = ?,
                    deployed_to_beekip = ?,
                    duration_seconds = ?,
                    status = ?
                WHERE cycle_id = ?
                """,
                (
                    sources_checked, new_urls_found, urls_accepted,
                    urls_rejected, deployed_count, duration_seconds,
                    status, cycle_id
                )
            )
            conn.commit()

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get aggregate metrics of the crawling pipeline."""
        with self.get_connection() as conn:
            sources_count = conn.execute("SELECT count(1) FROM monitored_sources WHERE status = 'ACTIVE'").fetchone()[0]
            queue_counts = dict(
                conn.execute("SELECT status, count(1) FROM inbound_queue GROUP BY status").fetchall()
            )
            total_blobs = conn.execute("SELECT count(1) FROM file_blobs").fetchone()[0]
            total_cycles = conn.execute("SELECT count(1) FROM monitoring_cycles_log").fetchone()[0]

            return {
                "active_sources": sources_count,
                "queue_counts": queue_counts,
                "total_file_blobs": total_blobs,
                "total_cycles_logged": total_cycles
            }
