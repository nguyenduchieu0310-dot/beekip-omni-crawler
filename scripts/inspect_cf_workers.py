import urllib.request
import json
import os
import pathlib

candidates = [
    pathlib.Path(os.environ.get('USERPROFILE', '')) / 'AppData' / 'Roaming' / 'xdg.config' / '.wrangler' / 'config' / 'default.toml',
    pathlib.Path.home() / '.wrangler' / 'config' / 'default.toml',
]

token = None
for p in candidates:
    if p.is_file():
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('oauth_token'):
                token = line.split('=', 1)[1].strip().strip('"').strip("'")
                break
        if token:
            break

print("Token extracted:", bool(token))
account_id = "f486ca0e5773032c7bf96c231489a0ea"

if token:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print("=== Cloudflare Workers Scripts ===")
            for item in data.get('result', []):
                print(f"  Worker: {item.get('id')} | Modified: {item.get('modified_on')}")
    except Exception as e:
        print("Error querying Workers scripts:", e)

    # Also check workers routes
    url_zones = f"https://api.cloudflare.com/client/v4/zones"
    req_zones = urllib.request.Request(url_zones, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req_zones) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print("\n=== Zones ===")
            for z in data.get('result', []):
                print(f"  Zone: {z.get('name')} | ID: {z.get('id')}")
                # Query routes for zone
                zone_id = z.get('id')
                url_routes = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/workers/routes"
                req_routes = urllib.request.Request(url_routes, headers={"Authorization": f"Bearer {token}"})
                try:
                    with urllib.request.urlopen(req_routes) as resp_r:
                        routes_data = json.loads(resp_r.read().decode('utf-8'))
                        for r in routes_data.get('result', []):
                            print(f"    Route: {r.get('pattern')} -> Worker: {r.get('script')}")
                except Exception as er:
                    print(f"    Error fetching routes for {z.get('name')}:", er)
    except Exception as e:
        print("Error querying Zones:", e)
