"""
MUNI84CR Railway worker — platform-backed crawl loop + HTTP health check.

Main thread:       HTTPServer on $PORT  (satisfies Railway health check)
Background thread: periodic discover + monitor passes via crawler-platform API

Env vars:
  PORT              Health check port (default 8080)
  DATABASE_URL      Observatory Postgres connection string
  PLATFORM_API_URL  Crawler-platform base URL (default http://localhost:3000)
  WORKER_DISCOVER   Set to "1" to run a discover pass before the monitor loop
  MONITOR_HOURS     Hours between monitor passes (default 6)
"""

import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

print("worker.py: STARTED", flush=True)

PORT = int(os.environ.get("PORT", 8080))
MONITOR_HOURS = float(os.environ.get("MONITOR_HOURS", "6"))
RETRY_DELAY = 60

_state = {
    "phase": "starting",
    "coverage": "?/?",
    "last_run": None,
    "status": "ok",
}


def _now() -> str:
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

    def log_message(self, *a):
        pass


# ── Pipeline thread ───────────────────────────────────────────────────────────

def get_coverage() -> tuple[int, int]:
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
    time.sleep(3)  # let HTTP server bind first
    print("[worker] Pipeline thread started", flush=True)

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
    log = logging.getLogger("worker")

    # ── init DB ──────────────────────────────────────────────────────────────
    try:
        from configs.init_db import init_db
    except Exception as e:
        log.error(f"[worker] import init_db failed: {e}")
        _state["status"] = f"import error: {e}"
        return

    db_url = os.environ.get("DATABASE_URL", "NOT SET")
    log.info(f"[worker] DATABASE_URL: {'set' if db_url != 'NOT SET' else 'NOT SET (SQLite)'}")

    if db_url != "NOT SET":
        import socket as _sock
        from urllib.parse import urlparse as _up
        u = _up(db_url)
        host, port = u.hostname, u.port or 5432
        log.info(f"[worker] TCP probe -> {host}:{port} ...")
        try:
            s = _sock.create_connection((host, port), timeout=15)
            s.close()
            log.info("[worker] TCP probe -> OK")
        except Exception as e:
            log.error(f"[worker] TCP probe failed: {e}")
            _state["status"] = f"tcp_fail: {e}"
            return

    _init_result: list = [None]

    def _run_init():
        try:
            init_db()
            _init_result[0] = "ok"
        except Exception as exc:
            _init_result[0] = exc

    t = threading.Thread(target=_run_init, daemon=True, name="init_db")
    t.start()
    t.join(timeout=25)
    if t.is_alive():
        log.error("[worker] init_db timed out after 25 s")
        _state["status"] = "init_db_timeout"
        return
    if isinstance(_init_result[0], Exception):
        log.error(f"[worker] init_db failed: {_init_result[0]}")
        _state["status"] = f"init_db error: {_init_result[0]}"
        return
    log.info("[worker] DB ready")

    # ── platform check ────────────────────────────────────────────────────────
    from modules.platform_client import PLATFORM_API_URL, CrawlerPlatformClient
    from modules import platform_runner
    from configs.db import get_connection
    from crawlers.crawl_all import load_municipalities

    log.info(f"[worker] Platform API: {PLATFORM_API_URL}")
    client = CrawlerPlatformClient()
    if not client.ping():
        log.error(f"[worker] Platform API unreachable at {PLATFORM_API_URL}")
        _state["status"] = "platform_unreachable"
        return
    log.info("[worker] Platform API -> reachable")

    munis_lookup = {m["id"]: m for m in load_municipalities(active_only=False)}

    def _select_ids(mode: str, only_missing: bool = False) -> list[str]:
        active = [m for m in load_municipalities(active_only=True)]
        conn = get_connection()
        try:
            indexed = {
                r["municipality_id"]
                for r in conn.execute("SELECT DISTINCT municipality_id FROM pages").fetchall()
            }
        finally:
            conn.close()
        if mode == "monitor":
            return [m["id"] for m in active if m["id"] in indexed]
        if only_missing:
            return [m["id"] for m in active if m["id"] not in indexed]
        return [m["id"] for m in active]

    def _submit(mode: str, only_missing: bool = False) -> int:
        ids = _select_ids(mode, only_missing=only_missing)
        if not ids:
            log.info(f"[worker] {mode}: nothing to submit")
            return 0
        job_map = platform_runner.submit_jobs(
            client, ids, munis_lookup, mode, log=log.info
        )
        log.info(f"[worker] {mode}: submitted {len(job_map)} job(s)")
        return len(job_map)

    # The reconcile loop is the heart of the proactive model: it continuously
    # syncs completed Observatory jobs into the DB and RE-RUNS empty/failed
    # municipalities (escalating to full rendering) without anyone waiting on
    # them — covering worker-, GHA-, and admin-started crawls alike.
    RECONCILE_SECONDS = int(os.environ.get("RECONCILE_SECONDS", "60"))

    # Optional discover-on-startup (owned by GHA by default; opt in explicitly).
    if os.environ.get("WORKER_DISCOVER"):
        _state["phase"] = "discover"
        _submit("discover", only_missing=True)

    _state["phase"] = "monitor"
    last_monitor = 0.0
    while True:
        try:
            summary = platform_runner.reconcile(client, munis_lookup, log=log.info)
            if any(summary.values()):
                log.info(f"[worker] reconcile: {summary}")
            i, t = get_coverage()
            _state.update(coverage=f"{i}/{t}", last_run=_now(), status="ok")
        except Exception as e:
            log.error(f"[worker] reconcile error: {e}")
            _state["status"] = f"error: {e}"

        # Kick off a fresh monitor pass every MONITOR_HOURS; the reconcile loop
        # above will sync + self-heal the results as they complete.
        now = time.monotonic()
        if now - last_monitor >= MONITOR_HOURS * 3600:
            log.info(f"[worker] Monitor pass — {_now()}")
            try:
                _submit("monitor")
            except Exception as e:
                log.error(f"[worker] monitor submit error: {e}")
            last_monitor = now

        time.sleep(RECONCILE_SECONDS)


# ── Entry point ───────────────────────────────────────────────────────────────

print(f"worker.py: binding to port {PORT}", flush=True)
threading.Thread(target=pipeline_loop, daemon=True, name="pipeline").start()
print("worker.py: starting HTTPServer...", flush=True)
server = HTTPServer(("0.0.0.0", PORT), _H)
print(f"worker.py: listening on port {PORT} — health check ready", flush=True)
server.serve_forever()
