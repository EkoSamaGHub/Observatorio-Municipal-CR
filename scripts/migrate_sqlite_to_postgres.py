#!/usr/bin/env python3
"""
One-time migration: copy all data from local SQLite to TigerData Postgres.

Usage:
    python scripts/migrate_sqlite_to_postgres.py

The script is idempotent — rows already in Postgres are skipped via
ON CONFLICT DO NOTHING.
"""
import os
import sqlite3
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import psycopg2
import psycopg2.extras

_SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "municipal.db"
_PG_URL = os.environ.get("DATABASE_URL", "")

# Order matters for FK integrity; page_links and page_diffs reference pages
TABLES = [
    "dev_sessions",
    "crawl_runs",
    "pages",
    "documents",
    "page_diffs",
    "page_links",
]

BATCH_SIZE = 2000


def migrate() -> None:
    if not _PG_URL:
        raise SystemExit("Set DATABASE_URL before running this script.")
    if not _SQLITE_PATH.exists():
        raise SystemExit(f"SQLite DB not found at {_SQLITE_PATH}")

    sqlite_conn = sqlite3.connect(_SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(_PG_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    pg_cur = pg_conn.cursor()

    for table in TABLES:
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table}: 0 rows -- skipping")
            continue

        cols = list(dict(rows[0]).keys())
        col_list = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT DO NOTHING"
        )

        inserted = 0
        for i in range(0, len(rows), BATCH_SIZE):
            batch = [tuple(row[c] for c in cols) for row in rows[i : i + BATCH_SIZE]]
            try:
                psycopg2.extras.execute_batch(pg_cur, sql, batch, page_size=BATCH_SIZE)
                inserted += pg_cur.rowcount if pg_cur.rowcount >= 0 else len(batch)
                pg_conn.commit()
                print(f"  {table}: {i + len(batch)}/{len(rows)} rows ...", end="\r")
            except Exception as e:
                print(f"\n  ERROR in {table} batch {i}: {e}")
                pg_conn.rollback()

        print(f"  {table}: {len(rows)} SQLite rows -> Postgres done          ")

    sqlite_conn.close()
    pg_conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
