"""Quick health check of all municipality root_urls."""
import json, asyncio, sys
import httpx

with open('municipalities.json', encoding='utf-8') as f:
    munis = json.load(f)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ObservatorioMuniCR/1.0; +https://observatoriomunicipalcr.org)"
}

async def check(client, m):
    url = m['root_url']
    try:
        r = await client.get(url, follow_redirects=True, timeout=20.0, headers=HEADERS)
        return (m['id'], m['name'], url, r.status_code, str(r.url) if str(r.url) != url else '', None)
    except Exception as e:
        return (m['id'], m['name'], url, None, '', f"{type(e).__name__}: {e}")

async def main():
    limits = httpx.Limits(max_connections=20)
    async with httpx.AsyncClient(limits=limits, verify=False) as client:
        results = await asyncio.gather(*(check(client, m) for m in munis))
    ok, redir, bad, err = [], [], [], []
    for r in results:
        mid, name, url, status, final, e = r
        if e:
            err.append(r)
        elif status and 200 <= status < 400:
            if final and final.rstrip('/') != url.rstrip('/'):
                redir.append(r)
            else:
                ok.append(r)
        else:
            bad.append(r)
    print(f"Total: {len(results)}  OK: {len(ok)}  Redirected: {len(redir)}  HTTP error: {len(bad)}  Conn error: {len(err)}")
    print("\n--- Redirected ---")
    for r in redir: print(f"  {r[0]} {r[3]} {r[2]} -> {r[4]}")
    print("\n--- HTTP errors ---")
    for r in bad: print(f"  {r[0]} {r[3]} {r[2]}  ({r[1]})")
    print("\n--- Connection / TLS errors ---")
    for r in err: print(f"  {r[0]} {r[2]}  ({r[1]}) :: {r[5]}")

asyncio.run(main())
