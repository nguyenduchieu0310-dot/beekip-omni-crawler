import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import get_cloudflare_token
from cloudflare.d1_deployer import CloudflareD1Deployer

d1 = CloudflareD1Deployer(api_token=get_cloudflare_token())
res = d1.execute_raw_sql("SELECT url, source_id, payload, retry_count FROM beekip_crawler_queue WHERE status = 'PENDING'")
rows = res['result'][0]['results']
print(f"Total PENDING items: {len(rows)}")
for idx, r in enumerate(rows, 1):
    payload = json.loads(r['payload']) if r.get('payload') else {}
    print(f"{idx}. [{r['source_id']}] {payload.get('title', 'No Title')}")
    print(f"   URL: {r['url']}")
