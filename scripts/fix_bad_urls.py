"""
One-time cleanup: delete crawl data collected under incorrect municipality URLs.

Corrected URLs:
  PU010 Corredores: corredores.go.cr -> municorredores.go.cr
  PU013 Puerto Jiménez: munipuertojimenez.go.cr -> munijimenez.go.cr

Run from project root:
  python scripts/fix_bad_urls.py [--dry-run]
"""

import sys
sys.path.insert(0, ".")

from configs.db import get_connection, BACKEND

DRY_RUN = "--dry-run" in sys.argv

BAD_DOMAINS = [
    "corredores.go.cr",
    "munipuertojimenez.go.cr",
]


def rows_deleted(conn, table: str, col: str, domain: str) -> int:
    like = f"%{domain}%"
    count = (conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {col} LIKE %s", (like,)).fetchone() or {}).get("n", 0)
    if not DRY_RUN and count:
        conn.execute(f"DELETE FROM {table} WHERE {col} LIKE %s", (like,))
    return count


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"fix_bad_urls.py [{mode}] — backend: {BACKEND}\n")

    conn = get_connection()
    total = 0

    for domain in BAD_DOMAINS:
        print(f"  domain: {domain}")
        for table, col in [
            ("pages",       "url"),
            ("documents",   "url"),
            ("page_diffs",  "url"),
            ("ssl_reports", "domain"),
            ("domain_expiry", "domain"),
        ]:
            n = rows_deleted(conn, table, col, domain)
            if n:
                verb = "would delete" if DRY_RUN else "deleted"
                print(f"    {verb} {n} rows from {table}.{col}")
            total += n

        # page_links has two URL columns
        for col in ("source_url", "target_url"):
            n = rows_deleted(conn, "page_links", col, domain)
            if n:
                verb = "would delete" if DRY_RUN else "deleted"
                print(f"    {verb} {n} rows from page_links.{col}")
            total += n

    if not DRY_RUN:
        conn.commit()
        print(f"\nCommitted. Total rows deleted: {total}")
    else:
        print(f"\nDry run complete. Would delete {total} rows total.")

    conn.close()


if __name__ == "__main__":
    main()
