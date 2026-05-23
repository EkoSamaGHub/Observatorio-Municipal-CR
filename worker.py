"""
Railway worker — permanent background process for the MUNI84CR pipeline.

Phase 1 (Discover): Runs `--only-missing` in a loop until all 84 municipalities
                    are indexed. Safe to restart at any point; already-indexed
                    municipalities are skipped automatically.

Phase 2 (Monitor):  Once coverage is 100%, re-checks every municipality every
                    MONITOR_INTERVAL_HOURS hours to detect content changes.

Deploy as a separate Railway service from the same repo:
  Start command: python -u worker.py
"""

import json
import time
import sys
from datetime import datetime, timezone

from configs.db import get_connection
from configs.init_db import init_db
from modules.logger import logger

# How often to re-run the monitor pass once fully indexed (hours)
MONITOR_INTERVAL_HOURS = 6

# Pause between discover retries when pipeline exits early (seconds)
DISCOVER_RETRY_DELAY = 60


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_coverage() -> tuple[int, int]:
    """Returns (indexed_count, total_count)."""
    with open("municipalities.json", "r", encoding="utf-8") as f:
        total = len(json.load(f))
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT municipality_id) FROM pages"
        ).fetchone()
        indexed = row[0] if row else 0
    finally:
        conn.close()
    return indexed, total


def run_discover():
    """Run one discover pass for missing municipalities."""
    # Import here so Railway logs show the import at run time, not startup
    from pipeline import run_pipeline
    logger.info(f"[worker] Starting discover pass — {_now()}")
    run_pipeline(mode="discover", only_missing=True)
    logger.info(f"[worker] Discover pass complete — {_now()}")


def run_monitor():
    """Run one monitor pass over all indexed municipalities."""
    from pipeline import run_pipeline
    logger.info(f"[worker] Starting monitor pass — {_now()}")
    run_pipeline(mode="monitor")
    logger.info(f"[worker] Monitor pass complete — {_now()}")


def main():
    logger.info("=" * 60)
    logger.info("MUNI84CR Worker starting up")
    logger.info("=" * 60)

    init_db()

    # ── Phase 1: Discover ────────────────────────────────────────
    while True:
        indexed, total = get_coverage()
        pct = indexed / total * 100 if total else 0
        logger.info(f"[worker] Coverage: {indexed}/{total} ({pct:.1f}%)")

        if indexed >= total:
            logger.info("[worker] 100% coverage reached! Switching to monitor mode.")
            break

        logger.info(f"[worker] {total - indexed} municipalities still missing. Running discover...")
        try:
            run_discover()
        except Exception as e:
            logger.error(f"[worker] Discover pass failed: {e}")
            logger.info(f"[worker] Retrying in {DISCOVER_RETRY_DELAY}s...")
            time.sleep(DISCOVER_RETRY_DELAY)
            continue

        # Brief pause before re-checking coverage
        time.sleep(10)

    # ── Phase 2: Monitor loop ────────────────────────────────────
    while True:
        try:
            run_monitor()
        except Exception as e:
            logger.error(f"[worker] Monitor pass failed: {e}")

        indexed, total = get_coverage()
        logger.info(f"[worker] Post-monitor coverage: {indexed}/{total}")
        logger.info(f"[worker] Next monitor pass in {MONITOR_INTERVAL_HOURS}h")
        time.sleep(MONITOR_INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("[worker] Interrupted. Goodbye.")
        sys.exit(0)
