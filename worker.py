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

print("worker.py: STARTED BUILD=cfefa39-PSYCOPG3", flush=True)

PORT = int(os.environ.get("PORT", 8080))
MONITOR_HOURS  = 6
RETRY_DELAY    = 60

_state = {"phase": "starting", "coverage": "?/?", "last_run": None, "status": "ok"}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _now_iso():
    # ISO format matches pipeline.py's started_at/finished_at so the duration
    # SQL (finished_at::timestamptz) and last_crawled comparisons stay valid.
    return datetime.now(timezone.utc).isoformat()


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

    # ── TCP connectivity check (fast fail if Timescale unreachable) ───────────
    if db_url != "NOT SET":
        import socket as _socket
        from urllib.parse import urlparse as _urlparse
        _u = _urlparse(db_url)
        _host, _port = _u.hostname, _u.port or 5432
        log.info(f"[worker] TCP probe → {_host}:{_port} ...")
        try:
            _s = _socket.create_connection((_host, _port), timeout=15)
            _s.close()
            log.info(f"[worker] TCP probe → OK (reachable)")
        except Exception as _e:
            log.error(f"[worker] TCP probe → FAILED: {_e}")
            log.error("[worker] Timescale unreachable from Railway — check IP allowlist / firewall")
            _state["status"] = f"tcp_fail: {_e}"
            return

    # ── init_db with a hard 25-second thread-level deadline ─────────────────
    # psycopg2's SSL negotiation can hang even with connect_timeout in the DSN;
    # this daemon thread guarantees we bail out and log a clear error.
    log.info("[worker] calling init_db() ...")
    _init_result: list = [None]   # [None] | ["ok"] | Exception
    def _run_init():
        try:
            init_db()
            _init_result[0] = "ok"
        except Exception as exc:
            _init_result[0] = exc
    _t = threading.Thread(target=_run_init, daemon=True, name="init_db")
    _t.start()
    _t.join(timeout=25)
    if _t.is_alive():
        log.error("[worker] init_db timed out after 25 s — check DB connectivity")
        _state["status"] = "init_db_timeout"
        return
    if isinstance(_init_result[0], Exception):
        log.error(f"[worker] init_db failed: {_init_result[0]}")
        _state["status"] = f"init_db error: {_init_result[0]}"
        return
    log.info("[worker] DB ready")

    from configs.db import get_connection
    from crawler_cli import drive_queue
    from modules import task_queue
    from pipeline import select_municipality_ids

    # ── Reap orphaned runs ────────────────────────────────────────────────────
    # Close legacy (task-less) runs left NULL by a previously killed process —
    # atexit never fires on SIGKILL — then finalize/requeue any task-based runs.
    try:
        c = get_connection()
        c.execute(
            "UPDATE crawl_runs SET finished_at=%s, status='done' "
            "WHERE finished_at IS NULL "
            "AND id NOT IN (SELECT DISTINCT run_id FROM crawl_tasks)",
            (_now_iso(),),
        )
        c.commit()
        c.close()
        task_queue.reap_all_active()
        log.info("[worker] reaped orphaned runs / requeued stale tasks")
    except Exception as e:
        log.error(f"[worker] orphan-run reap failed: {e}")

    # ── Background reaper ──────────────────────────────────────────────────────
    # Continuously requeues tasks abandoned by crashed workers (e.g. timed-out
    # GitHub Actions jobs) and finalizes runs once every task is terminal.
    def _reaper_loop():
        while True:
            try:
                task_queue.reap_all_active()
            except Exception as exc:
                log.error(f"[reaper] {exc}")
            time.sleep(300)
    threading.Thread(target=_reaper_loop, daemon=True, name="reaper").start()

    def _drive(mode: str, only_missing: bool, budget_hours: float):
        ids = select_municipality_ids(mode, only_missing=only_missing)
        if not ids:
            log.info(f"[worker] {mode}: nothing to enqueue")
            return
        run_id = task_queue.create_run(ids, mode, worker_id="railway")
        log.info(f"[worker] {mode} run {run_id}: {len(ids)} municipalities enqueued")
        try:
            prog = drive_queue(
                run_id, worker_id=f"railway-{os.getpid()}",
                time_budget=int(budget_hours * 3600),
                request_delay=2.0, max_pages=1000, max_depth=2,
            )
            _state["status"] = "ok"
            _state.update(coverage=f"{prog['done']}/{prog['total']} "
                                   f"(done={prog['done']} dead={prog['dead']})",
                          last_run=_now())
        except Exception as exc:
            log.error(f"[worker] {mode} run error: {exc}")
            _state["status"] = f"error: {exc}"

    # Phase 1 — discovery is OWNED BY GITHUB ACTIONS (the canonical crawler).
    # Running it here too would double the crawl load and the concurrent DB
    # connections, which can exhaust Timescale's limit and hang the API/SSR.
    # Opt in explicitly with WORKER_DISCOVER=1 only if Actions is unavailable.
    if os.environ.get("WORKER_DISCOVER"):
        _state["phase"] = "discover"
        _drive("discover", only_missing=True, budget_hours=6)

    # Phase 2 — periodic monitor passes (watchdog).
    _state["phase"] = "monitor"
    while True:
        log.info(f"[worker] Monitor pass — {_now()}")
        _drive("monitor", only_missing=False, budget_hours=MONITOR_HOURS)
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
