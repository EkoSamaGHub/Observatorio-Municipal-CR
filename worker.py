"""
Railway worker — permanent background process for the MUNI84CR pipeline.

Phase 1 (Discover): Runs `--only-missing` in a loop until all 84 municipalities
                    are indexed. Safe to restart at any point; already-indexed
                    municipalities are skipped automatically.

Phase 2 (Monitor):  Once coverage is 100%, re-checks every municipality every
                    MONITOR_INTERVAL_HOURS hours to detect content changes.

Deploy as a separate Railway service from the same repo:
  Start command: python -u worker.py
  Env var:       WORKER_MODE=1
"""

import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from configs.db import get_connection
from configs.init_db import init_db
from modules.logger import logger

# How often to re-run the monitor pass once fully indexed (hours)
MONITOR_INTERVAL_HOURS = 6

# Pause between discover retries when pipeline exits early (seconds)
DISCOVER_RETRY_DELAY = 60

# Current worker status — updated by main loop, served by health endpoint
_status = {"phase": "starting", "coverage": "?/?", "last_updated": None}


# ── Tiny health-check HTTP server ────────────────────────────────────────────
# Railway requires a process to bind $PORT or it marks the deployment failed.
# We run this in a background daemon thread so the main crawler thread can run.

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(_status).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # suppress per-request access logs


def _start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info(f"[worker] Health server listening on port {port}")
    server.serve_forever()


# ── Core helpers ─────────────────────────────────────────────────────────────

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
    from pipeline import run_pipeline
    logger.info(f"[worker] Starting discover pass — {_now()}")
    run_pipeline(mode="discover", only_missing=True)
    logger.info(f"[worker] Discover pass complete — {_now()}")


def run_monitor():
    from pipeline import run_pipeline
    logger.info(f"[worker] Starting monitor pass — {_now()}")
    run_pipeline(mode="monitor")
    logger.info(f"[worker] Monitor pass complete — {_now()}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("MUNI84CR Worker starting up")
    logger.info("=" * 60)

    # Start health-check server in background daemon thread
    t = threading.Thread(target=_start_health_server, daemon=True)
    t.start()

    init_db()

    # ── Phase 1: Discover ────────────────────────────────────────
    _status["phase"] = "discover"
    while True:
        indexed, total = get_coverage()
        pct = indexed / total * 100 if total else 0
        _status["coverage"] = f"{indexed}/{total}"
        _status["last_updated"] = _now()
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

        time.sleep(10)

    # ── Phase 2: Monitor loop ────────────────────────────────────
    _status["phase"] = "monitor"
    while True:
        try:
            run_monitor()
        except Exception as e:
            logger.error(f"[worker] Monitor pass failed: {e}")

        indexed, total = get_coverage()
        _status["coverage"] = f"{indexed}/{total}"
        _status["last_updated"] = _now()
        logger.info(f"[worker] Post-monitor coverage: {indexed}/{total}")
        logger.info(f"[worker] Next monitor pass in {MONITOR_INTERVAL_HOURS}h")
        time.sleep(MONITOR_INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("[worker] Interrupted. Goodbye.")
        sys.exit(0)
