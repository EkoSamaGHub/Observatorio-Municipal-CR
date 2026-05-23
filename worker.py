"""
Railway worker — permanent background process for the MUNI84CR pipeline.

Architecture:
  - Main thread:       tiny HTTP server on $PORT (keeps Railway's health check happy)
  - Background thread: the actual crawl pipeline (discover → monitor loop)

Phase 1 (Discover): Runs --only-missing until all 84 municipalities indexed.
Phase 2 (Monitor):  Re-checks all municipalities every MONITOR_INTERVAL_HOURS hours.

Deploy as a second Railway service from the same GitHub repo:
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

# Boot marker — confirms this version of worker.py is executing
print("=== MUNI84CR WORKER v3 BOOT ===", flush=True)
print(f"    cwd={os.getcwd()}  PORT={os.environ.get('PORT','?')}  WORKER_MODE={os.environ.get('WORKER_MODE','?')}", flush=True)

# ── Worker state (shared between HTTP thread and pipeline thread) ─────────────
_state = {
    "phase": "starting",
    "coverage": "?/?",
    "last_run": None,
    "status": "ok",
}

# How often to re-run the monitor pass once fully indexed (hours)
MONITOR_INTERVAL_HOURS = 6
DISCOVER_RETRY_DELAY   = 60   # seconds between discover retries


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ── Tiny health-check HTTP server ─────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(_state).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence per-request logs


# ── Pipeline logic ────────────────────────────────────────────────────────────

def get_coverage() -> tuple[int, int]:
    from configs.db import get_connection
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


def pipeline_loop():
    """Runs in a daemon background thread."""
    # Delay to ensure HTTP server has time to bind before we do heavy I/O
    time.sleep(2)

    from configs.init_db import init_db
    from modules.logger import logger
    from pipeline import run_pipeline

    logger.info("[worker] Pipeline thread started")

    try:
        init_db()
    except Exception as e:
        logger.error(f"[worker] init_db failed: {e}")
        _state["status"] = f"init_db error: {e}"
        return

    # ── Phase 1: Discover ────────────────────────────────────────
    _state["phase"] = "discover"
    while True:
        try:
            indexed, total = get_coverage()
        except Exception as e:
            logger.error(f"[worker] Coverage check failed: {e}")
            time.sleep(30)
            continue

        pct = indexed / total * 100 if total else 0
        _state["coverage"] = f"{indexed}/{total} ({pct:.1f}%)"
        _state["last_run"] = _now()
        logger.info(f"[worker] Coverage: {indexed}/{total} ({pct:.1f}%)")

        if indexed >= total:
            logger.info("[worker] 100% coverage — switching to monitor mode")
            break

        logger.info(f"[worker] {total - indexed} missing. Running discover pass...")
        try:
            run_pipeline(mode="discover", only_missing=True)
            logger.info("[worker] Discover pass complete")
        except Exception as e:
            logger.error(f"[worker] Discover pass error: {e}")
            _state["status"] = f"discover error: {e}"
            time.sleep(DISCOVER_RETRY_DELAY)

        time.sleep(10)

    # ── Phase 2: Monitor loop ────────────────────────────────────
    _state["phase"] = "monitor"
    while True:
        logger.info(f"[worker] Starting monitor pass — {_now()}")
        try:
            run_pipeline(mode="monitor")
            logger.info("[worker] Monitor pass complete")
            _state["status"] = "ok"
        except Exception as e:
            logger.error(f"[worker] Monitor pass error: {e}")
            _state["status"] = f"monitor error: {e}"

        try:
            indexed, total = get_coverage()
            _state["coverage"] = f"{indexed}/{total}"
            _state["last_run"] = _now()
        except Exception:
            pass

        logger.info(f"[worker] Sleeping {MONITOR_INTERVAL_HOURS}h until next monitor pass")
        time.sleep(MONITOR_INTERVAL_HOURS * 3600)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    port = int(os.environ.get("PORT", 8080))

    print(f"[worker] Starting health server on port {port}", flush=True)
    print("[worker] MUNI84CR Worker initializing...", flush=True)

    # Pipeline runs in background daemon thread
    t = threading.Thread(target=pipeline_loop, daemon=True, name="pipeline")
    t.start()

    # HTTP server runs in main thread — Railway's health check hits this
    server = HTTPServer(("0.0.0.0", port), _Handler)
    print(f"[worker] Health server ready — Railway can now hit port {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[worker] Interrupted.", flush=True)
        sys.exit(0)
