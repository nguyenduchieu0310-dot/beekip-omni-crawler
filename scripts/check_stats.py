import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import get_cloudflare_token
from cloudflare.d1_deployer import CloudflareD1Deployer

d1 = CloudflareD1Deployer(api_token=get_cloudflare_token())
res = d1.execute_raw_sql("SELECT status, count(*) as cnt FROM beekip_crawler_queue GROUP BY status")
print("=== Crawler Queue Status ===")
for r in res['result'][0]['results']:
    print(f"{r['status']}: {r['cnt']}")

res2 = d1.execute_raw_sql("SELECT count(*) as total_published FROM documents WHERE is_published = 1")
print("=== Total Published Documents ===")
print(res2['result'][0]['results'][0]['total_published'])

info = d1.execute_raw_sql("PRAGMA table_info(beekip_crawler_queue)")
print("\n=== Table Info beekip_crawler_queue ===")
for col in info['result'][0]['results']:
    print(col['name'], col['type'])

res4 = d1.execute_raw_sql("SELECT url, payload, error_message FROM beekip_crawler_queue WHERE status = 'NEEDS_OFFICE_CONVERTER'")
print("\n=== NEEDS_OFFICE_CONVERTER Items ===")
for r in res4['result'][0]['results']:
    payload = json.loads(r['payload']) if r.get('payload') else {}
    print(f"Title: {payload.get('title', r['url'])}")
    print(f"URL: {r['url']}")
    print(f"Error: {r['error_message']}")


