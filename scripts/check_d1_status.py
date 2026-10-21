import urllib.request, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import get_cloudflare_token, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_D1_DATABASE_ID

token = get_cloudflare_token()
print('Token found:', bool(token))
if token:
    url = f'https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/d1/database/{CLOUDFLARE_D1_DATABASE_ID}/query'
    req = urllib.request.Request(
        url,
        data=json.dumps({'sql': 'SELECT status, count(*) as cnt FROM beekip_crawler_queue GROUP BY status'}).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print('D1 Queue Status Summary:')
            for r in data['result'][0]['results']:
                print(f"  {r['status']}: {r['cnt']}")
    except Exception as e:
        print('Error querying D1:', e)

    req_pending = urllib.request.Request(
        url,
        data=json.dumps({'sql': "SELECT url, source_id, status, retry_count, payload FROM beekip_crawler_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 3"}).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req_pending) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print('\nNext Pending Documents to Process:')
            for r in data['result'][0]['results']:
                payload = json.loads(r['payload']) if r.get('payload') else {}
                print(f"[{r['source_id']}] {payload.get('title', r['url'])}")
                print(f"  URL: {r['url']}")
    except Exception as e:
        print('Error querying pending:', e)

