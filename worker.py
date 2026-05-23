"""
MUNI84CR Railway worker — crawl pipeline + HTTP health check.

Main thread:       HTTPServer on $PORT  (satisfies Railway health check)
Background thread: discover -> monitor pipeline loop

Start command: cd /app && python -u worker.py
Env vars:      WORKER_MODE=1  DATABASE_URL=<postgres url>
"""

import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

print("worker.py: STARTED BUILD=8f7ae6d-DIAG", flush=True)

PORT = int(os.environ.get("PORT", 8080))
MONITOR_HOURS  = 6
RETRY_DELAY    = 60

_state = {"phase": "starting", "coverage": "?/?", "last_run": None, "status": "ok"}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ── Health check HTTP server ──────────────────────────────────────────────────

class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(_state, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass


# ── Pipeline thread ───────────────────────────────────────────────────────────

def get_coverage():
    from configs.db import get_connection
    with open("municipalities.json", encoding="utf-8") as f:
        total = len(json.load(f))
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT municipality_id) AS cnt FROM pages"
        ).fetchone()
        indexed = list(row.values())[0] if row else 0
    finally:
        conn.close()
    return int(indexed), int(total)


def pipeline_loop():
    time.sleep(3)  # give HTTP server time to bind first
    print("[worker] Pipeline thread started", flush=True)

    # ── Granular import diagnostics (each step printed before+after) ──────────
    print("[worker] A: importing configs.init_db ...", flush=True)
    try:
        from configs.init_db import init_db
        print("[worker] A: OK", flush=True)
    except Exception as e:
        print(f"[worker] A: FAIL — {e}", flush=True)
        _state["status"] = f"import error (init_db): {e}"
        return

    print("[worker] B: importing scrapling.fetchers.Fetcher ...", flush=True)
    try:
        from scrapling.fetchers import Fetcher  # noqa — just testing import
        print("[worker] B: OK", flush=True)
    except Exception as e:
        print(f"[worker] B: FAIL — {e}", flush=True)
        _state["status"] = f"import error (scrapling): {e}"
        return

    print("[worker] C: importing pipeline.run_pipeline ...", flush=True)
    try:
        from pipeline import run_pipeline
        print("[worker] C: OK", flush=True)
    except Exception as e:
        print(f"[worker] C: FAIL — {e}", flush=True)
        _state["status"] = f"import error (pipeline): {e}"
        return

    print("[worker] ALL IMPORTS OK", flush=True)

    # Use stdlib logging directed to stdout (bypasses file handler in modules/logger)
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
    log = logging.getLogger("worker")
    log.info("[worker] Logging configured → stdout")

    db_url = os.environ.get("DATABASE_URL", "NOT SET")
    log.info(f"[worker] DATABASE_URL set: {'yes ('+db_url[:30]+'...)' if db_url != 'NOT SET' else 'NO — will use SQLite'}")
    try:
        init_db()
        log.info("[worker] DB ready")
    except Exception as e:
        log.error(f"[worker] init_db failed: {e}")
        _state["status"] = f"init_db error: {e}"
        return

    # Phase 1 — Discover until 84/84
    _state["phase"] = "discover"
    while True:
        try:
            indexed, total = get_coverage()
        except Exception as e:
            log.error(f"[worker] coverage check error: {e}")
            time.sleep(30)
            continue

        pct = indexed / total * 100 if total else 0
        _state.update(coverage=f"{indexed}/{total} ({pct:.1f}%)", last_run=_now())
        log.info(f"[worker] Coverage: {indexed}/{total} ({pct:.1f}%)")

        if indexed >= total:
            log.info("[worker] 100% coverage — switching to monitor mode")
            break

        log.info(f"[worker] {total - indexed} missing — running discover...")
        try:
            run_pipeline(mode="discover", only_missing=True)
            _state["status"] = "ok"
        except Exception as e:
            log.error(f"[worker] discover error: {e}")
            _state["status"] = f"error: {e}"
            time.sleep(RETRY_DELAY)
        time.sleep(10)

    # Phase 2 — Monitor every N hours
    _state["phase"] = "monitor"
    while True:
        log.info(f"[worker] Monitor pass — {_now()}")
        try:
            run_pipeline(mode="monitor")
            _state["status"] = "ok"
        except Exception as e:
            log.error(f"[worker] monitor error: {e}")
            _state["status"] = f"error: {e}"

        try:
            i, t = get_coverage()
            _state.update(coverage=f"{i}/{t}", last_run=_now())
        except Exception:
            pass

        log.info(f"[worker] Sleeping {MONITOR_HOURS}h")
        time.sleep(MONITOR_HOURS * 3600)


# ── Entry point ───────────────────────────────────────────────────────────────

print(f"worker.py: binding to port {PORT}", flush=True)
print(f"worker.py: WORKER_MODE={os.environ.get('WORKER_MODE', 'NOT SET')}", flush=True)

threading.Thread(target=pipeline_loop, daemon=True, name="pipeline").start()

print("worker.py: starting HTTPServer...", flush=True)
server = HTTPServer(("0.0.0.0", PORT), _H)
print(f"worker.py: listening on port {PORT} — health check ready", flush=True)
server.serve_forever()
