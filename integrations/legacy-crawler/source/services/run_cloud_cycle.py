"""
Headless Cloud Delta Runner for Beekip.
Designed to run in GitHub Actions Scheduled Cronjobs or headless cloud environments.
Scans active sources for documents >= 2023, sanitizes, and deploys directly to Cloudflare R2 + D1.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Ensure UTF-8 output
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [CloudRunner] %(message)s"
)
logger = logging.getLogger("beekip.cloud_runner")


def verify_private_app_route(d1, cloudflare_session, bucket_api, app_url):
    """Prove the public cover route reads the selected private bucket, without writes."""
    import hashlib
    import requests
    from urllib.parse import quote, urlparse
    parsed = urlparse(app_url)
    if (parsed.scheme != 'https' or parsed.netloc != 'tailieu.beekip.vn'
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise RuntimeError('Expected the verified Beekip app origin https://tailieu.beekip.vn')
    rows = d1.execute_raw_sql('SELECT id,slug FROM documents WHERE is_published=1 AND archived_at IS NULL AND cover_url IS NOT NULL LIMIT 3')['result'][0]['results']
    def digest(response):
        if response.status_code != 200:
            response.close()
            return None
        size, hasher = 0, hashlib.sha256()
        try:
            for block in response.iter_content(65536):
                size += len(block)
                if size > 2 * 1024 * 1024:
                    return None
                hasher.update(block)
            return hasher.digest() if size else None
        finally:
            response.close()
    for row in rows:
        object_path = '/objects/documents/v1/' + quote(row['id'], safe='') + '/cover.jpg'
        private_digest = digest(cloudflare_session.get(bucket_api + object_path, timeout=20, stream=True))
        if private_digest is None:
            continue
        public_url = app_url.rstrip('/') + '/api/documents/' + quote(row['slug'], safe='') + '/cover'
        # Deliberately use a separate request: never send Cloudflare credentials to the website.
        public_digest = digest(requests.get(public_url, timeout=20, stream=True, allow_redirects=False))
        if public_digest == private_digest:
            return
    raise RuntimeError('Could not verify Beekip cover route against the selected private R2 bucket')

def preflight(local_read_only=False):
    import requests
    from core import config
    from cloudflare.d1_deployer import CloudflareD1Deployer
    names = ('CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_D1_DATABASE_ID',
             'CLOUDFLARE_R2_BUCKET', 'CLOUDFLARE_API_TOKEN')
    if not local_read_only:
        missing = [name for name in names if not os.environ.get(name, '').strip()]
        if missing:
            raise RuntimeError('Missing repository secrets: ' + ', '.join(missing))
    token = config.get_cloudflare_token()
    if not token:
        raise RuntimeError('No Cloudflare credential available')
    d1 = CloudflareD1Deployer(api_token=token)
    columns = d1._get_columns()
    required = {'id', 'slug', 'source_object_key', 'cover_url', 'is_published', 'audience_tags_json'}
    if not required <= columns:
        raise RuntimeError('D1 schema is incompatible with this publisher')
    session = requests.Session()
    session.headers['Authorization'] = 'Bearer ' + token
    bucket_api = f'https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}/r2/buckets/{config.CLOUDFLARE_R2_BUCKET}'
    def read(path):
        response = session.get(bucket_api + path, timeout=20)
        if response.status_code != 200:
            raise RuntimeError(f'Cloudflare preflight HTTP {response.status_code}')
        data = response.json()
        if not data.get('success'):
            raise RuntimeError('Cloudflare preflight returned success=false')
        return data['result']
    read('')
    verify_private_app_route(d1, session, bucket_api, config.BEEKIP_BASE_URL)
    # Authenticated local OAuth is allowed for this read-only check, never exported as a secret.
    logger.info('Preflight passed: D1 schema, private R2 bucket and existing Beekip cover route')
    return d1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('preflight', 'ingest'), default='preflight')
    parser.add_argument('--local-read-only', action='store_true')
    args = parser.parse_args()
    if args.local_read_only and args.mode != 'preflight':
        parser.error('--local-read-only is restricted to preflight')
    try:
        if args.mode == "ingest":
            from cloudflare.document_ingest import ingest_config
            ingest_config()
        d1 = preflight(args.local_read_only)
        if args.mode == 'preflight':
            return 0
        if os.getenv('BEEKIP_CLOUD_ENABLED') != 'true':
            raise RuntimeError('Set BEEKIP_CLOUD_ENABLED=true after verifying billing limits and preflight')
        from cloudflare.cloud_ledger import CloudLedger
        from cloudflare.r2_uploader import CloudflareR2Uploader
        from services.cloud_pipeline import CloudPipeline
        from services.omni_scheduler import OmniSchedulerDaemon
        ledger = CloudLedger(d1)
        ledger.initialize()
        pipeline = CloudPipeline(ledger, CloudflareR2Uploader(), d1)
        daemon = OmniSchedulerDaemon(db=ledger, pipeline=pipeline)
        try:
            result = daemon.run_single_cycle(
                max_items_per_cycle=3,
                max_attempts_per_cycle=12,
                scan_budget_seconds=120,
            )
        finally:
            daemon.worker_pool.shutdown(wait=True)
        report = json.dumps(result, ensure_ascii=False, indent=2)
        logger.info('Cloud result: %s', report)
        summary_path = os.getenv('GITHUB_STEP_SUMMARY')
        if summary_path:
            with open(summary_path, 'a', encoding='utf-8') as summary:
                summary.write('Beekip ingestion result\n\n```json\n' + report + '\n```\n')
        # Individual sources routinely throttle or time out. Keep them visible in
        # the report, but fail only when the whole scan is unavailable or a real
        # document-processing attempt fails.
        return 1 if result['failed_count'] or not result['sources_checked'] else 0
    except Exception as exc:
        logger.error('Cloud cycle stopped: %s', str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
