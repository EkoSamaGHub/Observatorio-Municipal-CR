"""
WHOIS domain expiry checker — populates domain_expiry table for all active municipalities.

Usage:
    python scripts/check_domains.py [--limit N]

Looks up WHOIS records for each municipality domain and stores the registrar,
creation date, and expiry date in the DB.
"""

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from configs.db import BACKEND, get_connection

BETWEEN_HOSTS = 2  # seconds between WHOIS queries


def load_municipalities() -> list[dict]:
    path = ROOT / "municipalities.json"
    return json.loads(path.read_text(encoding="utf-8"))


def extract_domain(url: str) -> str:
    return urlparse(url).hostname or ""


def _to_iso(value) -> str | None:
    """Normalize a WHOIS date field (datetime, list[datetime], or str) to ISO 8601."""
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def lookup_whois(domain: str) -> dict:
    try:
        import whois  # python-whois
        w = whois.whois(domain)
        return {
            "registrar":      (w.registrar or "").strip() or None,
            "expiry_date":    _to_iso(w.expiration_date),
            "creation_date":  _to_iso(w.creation_date),
        }
    except Exception as e:
        print(f"  [error] whois({domain}): {e}")
        return {"registrar": None, "expiry_date": None, "creation_date": None}


def upsert(conn, municipality_id: str, domain: str, info: dict, checked_at: str) -> None:
    if BACKEND == "postgres":
        conn.execute("""
            INSERT INTO domain_expiry (municipality_id, domain, registrar, expiry_date, creation_date, checked_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (municipality_id, domain) DO UPDATE SET
                registrar=EXCLUDED.registrar, expiry_date=EXCLUDED.expiry_date,
                creation_date=EXCLUDED.creation_date, checked_at=EXCLUDED.checked_at
        """, (municipality_id, domain, info["registrar"], info["expiry_date"], info["creation_date"], checked_at))
    else:
        conn.execute("""
            INSERT OR REPLACE INTO domain_expiry
                (municipality_id, domain, registrar, expiry_date, creation_date, checked_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (municipality_id, domain, info["registrar"], info["expiry_date"], info["creation_date"], checked_at))
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="WHOIS lookup for all municipality domains")
    parser.add_argument("--limit", type=int, default=0, help="Max number of municipalities to check (0=all)")
    args = parser.parse_args()

    municipalities = [m for m in load_municipalities() if m.get("active")]
    if args.limit:
        municipalities = municipalities[: args.limit]

    print(f"Checking WHOIS for {len(municipalities)} municipalities…")
    conn = get_connection()

    for i, muni in enumerate(municipalities, 1):
        domain = extract_domain(muni["root_url"])
        if not domain:
            print(f"[{i}/{len(municipalities)}] {muni['name']} — skipped (no domain)")
            continue

        print(f"[{i}/{len(municipalities)}] {muni['name']} ({domain})")
        info = lookup_whois(domain)
        checked_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        upsert(conn, muni["id"], domain, info, checked_at)
        print(f"  → expiry={info['expiry_date']}  registrar={info['registrar']}")

        if i < len(municipalities):
            time.sleep(BETWEEN_HOSTS)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
