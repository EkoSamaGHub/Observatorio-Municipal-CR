#!/usr/bin/env python3
"""
Log developer hours toward building MUNI84CR.

Usage:
    python log_hours.py 3.5 "Built pipeline and crawler"
    python log_hours.py 2   "Designed database schema"
    python log_hours.py --list
    python log_hours.py --total
"""
import argparse
import sys
from datetime import datetime, timezone

from configs.db import get_connection
from configs.init_db import init_db


def log(hours: float, note: str) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO dev_sessions (logged_at, hours, note) VALUES (%s, %s, %s)",
        (datetime.now(timezone.utc).isoformat(), hours, note),
    )
    conn.commit()

    total = conn.execute(
        "SELECT COALESCE(SUM(hours), 0) AS total FROM dev_sessions"
    ).fetchone()["total"]
    conn.close()
    print(f"OK Logged {hours}h - \"{note}\"")
    print(f"  Total dev investment: {total:.1f}h")


def list_sessions() -> None:
    conn = get_connection()
    rows = conn.execute(
        "SELECT logged_at, hours, note FROM dev_sessions ORDER BY logged_at DESC"
    ).fetchall()
    conn.close()

    if not rows:
        print("No sessions logged yet.")
        return

    print(f"{'Date':<22} {'Hours':>6}  Note")
    print("-" * 60)
    for r in rows:
        dt = datetime.fromisoformat(r["logged_at"]).strftime("%Y-%m-%d %H:%M")
        print(f"{dt:<22} {r['hours']:>6.1f}h  {r['note'] or ''}")


def total() -> None:
    conn = get_connection()
    t = conn.execute(
        "SELECT COALESCE(SUM(hours), 0) AS total FROM dev_sessions"
    ).fetchone()["total"]
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM dev_sessions"
    ).fetchone()["n"]
    conn.close()
    print(f"Total: {t:.1f}h across {n} session(s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log dev hours for MUNI84CR")
    parser.add_argument("hours", nargs="?", type=float, help="Hours spent")
    parser.add_argument("note", nargs="?", default="", help="What you worked on")
    parser.add_argument("--list", action="store_true", help="List all sessions")
    parser.add_argument("--total", action="store_true", help="Show total hours")
    args = parser.parse_args()

    if args.list:
        list_sessions()
    elif args.total:
        total()
    elif args.hours is not None:
        log(args.hours, args.note)
    else:
        parser.print_help()
        sys.exit(1)
