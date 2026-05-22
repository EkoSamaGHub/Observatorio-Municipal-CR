"""
SSL Labs scanner — populates ssl_reports table for all active municipalities.

Usage:
    python scripts/check_ssl.py [--limit N]

Calls the SSL Labs API (free, no key required) for each municipality domain,
polls until the scan is READY, then stores the grade and cert expiry in the DB.
Rate-limited: one scan at a time with delays to respect SSL Labs terms of use.
"""

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from configs.db import BACKEND, get_connection

SSLLABS_API = "https://api.ssllabs.com/api/v3/analyze"
POLL_INTERVAL = 15   # seconds between status polls
SCAN_TIMEOUT  = 300  # seconds before giving up on a single host
BETWEEN_HOSTS = 5    # seconds between starting new scans


def load_municipalities() -> list[dict]:
    path = ROOT / "municipalities.json"
    return json.loads(path.read_text(encoding="utf-8"))


def extract_domain(url: str) -> str:
    return urlparse(url).hostname or ""


def epoch_ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def start_scan(domain: str) -> dict | None:
    try:
        r = requests.get(SSLLABS_API, params={"host": domain, "startNew": "on", "all": "done"}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [error] start_scan({domain}): {e}")
        return None


def poll_scan(domain: str) -> dict | None:
    try:
        r = requests.get(SSLLABS_API, params={"host": domain, "all": "done"}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [error] poll_scan({domain}): {e}")
        return None


def wait_for_ready(domain: str) -> dict | None:
    data = start_scan(domain)
    if not data:
        return None

    deadline = time.time() + SCAN_TIMEOUT
    while time.time() < deadline:
        status = data.get("status", "")
        if status == "READY":
            return data
        if status == "ERROR":
            print(f"  [ssl-labs] ERROR status for {domain}: {data.get('statusMessage')}")
            return None
        print(f"  [ssl-labs] {domain} status={status} — waiting {POLL_INTERVAL}s…")
        time.sleep(POLL_INTERVAL)
        data = poll_scan(domain)
        if not data:
            return None

    print(f"  [timeout] {domain} did not complete within {SCAN_TIMEOUT}s")
    return None


def extract_results(data: dict) -> dict:
    endpoints = data.get("endpoints", [])
    if not endpoints:
        return {"grade": None, "cert_expiry": None, "ip_address": None, "has_warnings": False}

    ep = endpoints[0]
    grade = ep.get("grade")
    ip_address = ep.get("ipAddress")
    has_warnings = bool(ep.get("hasWarnings", False))

    cert_expiry = None
    # Try details.cert.notAfter first, fall back to details.cert.subject expiry fields
    details = ep.get("details") or {}
    cert = details.get("cert") or {}
    not_after = cert.get("notAfter") or details.get("notAfter")
    if not_after:
        try:
            cert_expiry = epoch_ms_to_iso(int(not_after))
        except (ValueError, TypeError):
            pass
    # Some responses embed expiry directly on the endpoint as certExpiry (epoch ms)
    if not cert_expiry:
        raw = ep.get("certExpiry") or ep.get("details", {}).get("certExpiry")
        if raw:
            try:
                cert_expiry = epoch_ms_to_iso(int(raw))
            except (ValueError, TypeError):
                pass

    return {"grade": grade, "cert_expiry": cert_expiry, "ip_address": ip_address, "has_warnings": has_warnings}


def upsert(conn, municipality_id: str, domain: str, results: dict, checked_at: str) -> None:
    has_warnings = 1 if results["has_warnings"] else 0
    if BACKEND == "postgres":
        conn.execute("""
            INSERT INTO ssl_reports (municipality_id, domain, grade, cert_expiry, ip_address, has_warnings, checked_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (municipality_id, domain) DO UPDATE SET
                grade=EXCLUDED.grade, cert_expiry=EXCLUDED.cert_expiry,
                ip_address=EXCLUDED.ip_address, has_warnings=EXCLUDED.has_warnings,
                checked_at=EXCLUDED.checked_at
        """, (municipality_id, domain, results["grade"], results["cert_expiry"],
              results["ip_address"], has_warnings, checked_at))
    else:
        conn.execute("""
            INSERT OR REPLACE INTO ssl_reports
                (municipality_id, domain, grade, cert_expiry, ip_address, has_warnings, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (municipality_id, domain, results["grade"], results["cert_expiry"],
              results["ip_address"], has_warnings, checked_at))
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SSL Labs scans for all municipalities")
    parser.add_argument("--limit", type=int, default=0, help="Max number of municipalities to scan (0=all)")
    args = parser.parse_args()

    municipalities = [m for m in load_municipalities() if m.get("active")]
    if args.limit:
        municipalities = municipalities[: args.limit]

    print(f"Scanning {len(municipalities)} municipalities via SSL Labs API…")
    conn = get_connection()

    for i, muni in enumerate(municipalities, 1):
        domain = extract_domain(muni["root_url"])
        if not domain:
            print(f"[{i}/{len(municipalities)}] {muni['name']} — skipped (no domain)")
            continue

        print(f"[{i}/{len(municipalities)}] {muni['name']} ({domain})")
        data = wait_for_ready(domain)
        checked_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if data:
            results = extract_results(data)
            upsert(conn, muni["id"], domain, results, checked_at)
            print(f"  grade={results['grade']}  cert_expiry={results['cert_expiry']}")
        else:
            upsert(conn, muni["id"], domain, {"grade": None, "cert_expiry": None, "ip_address": None, "has_warnings": False}, checked_at)
            print(f"  scan failed, stored null grade")

        if i < len(municipalities):
            time.sleep(BETWEEN_HOSTS)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
