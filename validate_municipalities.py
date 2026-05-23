"""
Validate municipality URLs — detect bad root_url entries.
Tests each URL to see if it responds and is reachable.
"""

import json
import sys
from urllib.parse import urljoin
from scrapling.fetchers import Fetcher

fetcher = Fetcher()

with open("municipalities.json", "r", encoding="utf-8") as f:
    municipalities = json.load(f)

bad_urls = []
redirects = []
ok_urls = []

print(f"Validating {len(municipalities)} municipalities...\n")

for muni in municipalities:
    muni_id = muni["id"]
    name = muni["name"]
    root_url = muni["root_url"]

    try:
        # Try to fetch root URL
        response = fetcher.get(root_url, verify=False, timeout=10)

        final_url = response.url if hasattr(response, 'url') else root_url
        status = response.status if hasattr(response, 'status') else "unknown"

        if status >= 400:
            print(f"[BAD]      {muni_id:8s} ({status}) {name}")
            print(f"   URL: {root_url}")
            bad_urls.append((muni_id, name, root_url, status))
        elif final_url != root_url:
            print(f"[REDIRECT] {muni_id:8s} {name}")
            print(f"   Registered: {root_url}")
            print(f"   Actual:     {final_url}")
            redirects.append((muni_id, name, root_url, final_url))
        else:
            print(f"[OK]       {muni_id:8s} {name}")
            ok_urls.append(muni_id)

    except Exception as e:
        print(f"[ERROR]    {muni_id:8s} {name}")
        print(f"   {str(e)[:80]}")
        bad_urls.append((muni_id, name, root_url, str(e)))

print(f"\n{'='*80}")
print(f"Summary:")
print(f"  [OK]       {len(ok_urls)}")
print(f"  [REDIRECT] {len(redirects)}")
print(f"  [BAD]      {len(bad_urls)}")

if redirects:
    print(f"\n{'='*80}")
    print("Redirects (need investigation):")
    for muni_id, name, registered, actual in redirects:
        print(f"\n  {muni_id} - {name}")
        print(f"    Current:  {registered}")
        print(f"    Resolves: {actual}")

if bad_urls:
    print(f"\n{'='*80}")
    print("Bad URLs (unreachable or 4xx/5xx):")
    for muni_id, name, url, status in bad_urls:
        print(f"  {muni_id:8s} - {name}")
        print(f"    {url}")
        print(f"    Status: {status}")
