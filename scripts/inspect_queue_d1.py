import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import get_cloudflare_token
from cloudflare.d1_deployer import CloudflareD1Deployer

token = get_cloudflare_token()
d1 = CloudflareD1Deployer(api_token=token)

print("=== 1. Summary by Status ===")
res = d1.execute_raw_sql("SELECT status, count(*) as cnt FROM beekip_crawler_queue GROUP BY status")
for row in res['result'][0]['results']:
    print(f"  {row['status']}: {row['cnt']}")

print("\n=== 2. Oldest PENDING items (Next in line to process) ===")
res_pending = d1.execute_raw_sql("SELECT url, source_id, status, retry_count, error_message, created_at, payload FROM beekip_crawler_queue WHERE status IN ('PENDING', 'FAILED') AND retry_count < 3 ORDER BY created_at ASC, url ASC LIMIT 10")
for row in res_pending['result'][0]['results']:
    payload = json.loads(row['payload']) if row.get('payload') else {}
    print(f"[{row['status']}] [{row['source_id']}] {payload.get('title', row['url'])}")
    print(f"  URL: {row['url']}")
    print(f"  Created: {row['created_at']} | Retries: {row['retry_count']} | Error: {row['error_message']}")

print("\n=== 3. Latest Published Documents (in `documents` table) ===")
res_docs = d1.execute_raw_sql("SELECT id, title, slug, created_at, cover_url FROM documents ORDER BY created_at DESC LIMIT 5")
for row in res_docs['result'][0]['results']:
    print(f"* [{row['created_at']}] {row['title']}")
    print(f"  https://tailieu.beekip.vn/tai-lieu/{row['slug']}")
    print(f"  Cover: {row['cover_url']}")
