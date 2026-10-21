"""Small durable D1 ledger, independent of runner disk and Actions caches."""
import json
from pathlib import Path
from core.config import SOURCES_REGISTRY_PATH


class CloudLedger:
    def __init__(self, client):
        self.client = client
        self.sources = []

    def query(self, sql, params=None):
        return self.client.execute_raw_sql(sql, params)['result'][0].get('results', [])

    def initialize(self):
        for sql in (
            "CREATE TABLE IF NOT EXISTS beekip_crawler_queue (url TEXT PRIMARY KEY, source_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', retry_count INTEGER NOT NULL DEFAULT 0, error_message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
            "CREATE INDEX IF NOT EXISTS beekip_crawler_queue_status ON beekip_crawler_queue(status,retry_count,created_at)",
            "CREATE TABLE IF NOT EXISTS beekip_crawler_sources (source_id TEXT PRIMARY KEY,last_etag TEXT,last_modified_header TEXT,last_checked_at TEXT)",
            "CREATE TABLE IF NOT EXISTS beekip_crawler_blobs (sha256_hash TEXT PRIMARY KEY,file_size_bytes INTEGER NOT NULL,r2_storage_key TEXT NOT NULL,public_file_url TEXT NOT NULL,first_seen_url TEXT)",
        ):
            self.query(sql)
        self.query("UPDATE beekip_crawler_queue SET status='PENDING' WHERE status='PROCESSING'")

    def sync_sources_from_json(self, registry_file=SOURCES_REGISTRY_PATH):
        self.sources = json.loads(Path(registry_file).read_text(encoding='utf-8'))
        return len(self.sources)

    def get_active_sources(self):
        state = {r['source_id']: r for r in self.query('SELECT * FROM beekip_crawler_sources')}
        active = [dict(src, **{k: v for k, v in state.get(src['source_id'], {}).items() if k != 'source_id'})
                  for src in self.sources if src.get('status') == 'ACTIVE']
        return sorted(active, key=lambda s: (s.get('last_checked_at') or '', s['source_id']))

    def update_source_sync_meta(self, source_id, etag=None, last_modified=None, **kwargs):
        self.query('INSERT INTO beekip_crawler_sources VALUES (?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(source_id) DO UPDATE SET last_etag=COALESCE(excluded.last_etag,last_etag),last_modified_header=COALESCE(excluded.last_modified_header,last_modified_header),last_checked_at=excluded.last_checked_at', [source_id, etag, last_modified])

    def enqueue_inbound_items(self, items):
        for item in items:
            self.query('INSERT INTO beekip_crawler_queue (url,source_id,payload,status) VALUES (?,?,?,?) ON CONFLICT(url) DO NOTHING',
                       [item['url'], item['source_id'], json.dumps(item, ensure_ascii=False), item.get('status', 'PENDING')])
        return len(items)

    def get_pending_inbound_items(self, limit=3, **kwargs):
        rows = self.query("SELECT payload FROM beekip_crawler_queue WHERE status IN ('PENDING','FAILED') AND retry_count<3 ORDER BY created_at,url LIMIT ?", [limit])
        return [json.loads(row['payload']) for row in rows]

    def update_inbound_status(self, url, status, error_message=None, increment_retry=False):
        self.query('UPDATE beekip_crawler_queue SET status=?,error_message=?,retry_count=retry_count+? WHERE url=?',
                   [status, error_message, int(increment_retry), url])

    def get_blob_by_hash(self, sha256):
        rows = self.query('SELECT * FROM beekip_crawler_blobs WHERE sha256_hash=?', [sha256])
        return rows[0] if rows else None

    def record_file_blob(self, sha256_hash, file_size_bytes, r2_storage_key, public_file_url, first_seen_url=None):
        self.query('INSERT INTO beekip_crawler_blobs VALUES (?,?,?,?,?) ON CONFLICT(sha256_hash) DO NOTHING',
                   [sha256_hash, file_size_bytes, r2_storage_key, public_file_url, first_seen_url])

    def stored_bytes(self):
        return self.query('SELECT COALESCE(SUM(file_size_bytes),0) AS total FROM beekip_crawler_blobs')[0]['total']

    def create_monitoring_cycle(self, cycle_id):
        pass

    def complete_monitoring_cycle(self, **kwargs):
        pass
