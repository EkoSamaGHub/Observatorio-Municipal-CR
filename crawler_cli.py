"""
Crawler queue CLI — the single entrypoint for the task-queue architecture.

Subcommands:
  enqueue   Create a run and one task per municipality (producer).
  work      Claim and process tasks until drained or time budget hit (worker).
  reap      Requeue dead-worker tasks / mark exhausted ones dead / finalize.
  progress  Print run progress as JSON.

Designed so GitHub Actions can run `enqueue` once, fan out N parallel `work`
jobs against the same run, then `reap` to finalize. Workers are safe to run in
parallel (Postgres SELECT ... FOR UPDATE SKIP LOCKED) and recover from crashes
(expired leases are reclaimed).
"""

import argparse
import json
import os
import socket
import time
import uuid

from configs.db import get_connection
from configs.init_db import init_db
from crawlers.crawl_all import load_municipalities
from crawlers.scrapling_crawler import ScraplingCrawler
from modules import task_queue
from modules.logger import logger
from pipeline import crawl_one_municipality, select_municipality_ids


def _worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def _emit_github_output(key: str, value) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def _latest_active_run() -> int | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM crawl_runs WHERE status='running' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return int(row["id"]) if row else None


# ── drive_queue: the worker loop ─────────────────────────────────────────────────

def drive_queue(run_id: int, worker_id: str, time_budget: int = 3000,
                request_delay: float = 1.0, max_pages: int = 200, max_depth: int = 2,
                lease_seconds: int = 900) -> dict:
    lookup = {m["id"]: m for m in load_municipalities(active_only=False)}
    crawler = ScraplingCrawler(request_delay=request_delay, max_pages=max_pages,
                               respect_robots=True, verify_ssl=False)
    start = time.monotonic()
    processed = 0

    logger.info(f"[{worker_id}] worker started on run {run_id} (budget={time_budget}s)")

    while True:
        if time.monotonic() - start > time_budget:
            logger.info(f"[{worker_id}] time budget reached, stopping")
            break

        task = task_queue.claim_task(run_id, worker_id, lease_seconds=lease_seconds)
        if not task:
            logger.info(f"[{worker_id}] no claimable tasks left")
            break

        task_id = task["id"]
        muni_id = task["municipality_id"]
        muni = lookup.get(muni_id)
        if not muni:
            task_queue.fail_task(task_id, f"unknown municipality_id {muni_id}")
            continue

        logger.info(f"[{worker_id}] claimed {muni_id} (task {task_id}, attempt {task['attempts']})")
        try:
            def hb(pages, _tid=task_id):
                task_queue.heartbeat(_tid, worker_id, lease_seconds, pages)

            stats = crawl_one_municipality(
                muni, crawler, task["mode"], max_depth, max_pages, on_progress=hb
            )
            task_queue.complete_task(
                task_id, pages_found=stats["fetched"],
                sitemap_total=stats["sitemap_total"], completeness_pct=stats["completeness"],
            )
            processed += 1
            logger.info(f"[{worker_id}] done {muni_id}: fetched={stats['fetched']} "
                        f"new={stats['new']} errors={stats['errors']}")
        except Exception as e:
            logger.error(f"[{worker_id}] {muni_id} failed: {e}")
            task_queue.fail_task(task_id, str(e))

    prog = task_queue.reap_run(run_id)
    logger.info(f"[{worker_id}] stopped — processed {processed}; run progress: {prog}")
    return prog


# ── Subcommands ──────────────────────────────────────────────────────────────────

def cmd_enqueue(args) -> None:
    init_db()
    ids = select_municipality_ids(args.mode, only_missing=args.only_missing, ids=args.ids)
    if not ids:
        logger.info("enqueue: no municipalities match — nothing to do")
        _emit_github_output("run_id", "")
        _emit_github_output("count", "0")
        return
    run_id = task_queue.create_run(ids, args.mode, max_attempts=args.max_attempts)
    logger.info(f"enqueue: run {run_id} created with {len(ids)} tasks (mode={args.mode})")
    print(run_id)
    _emit_github_output("run_id", run_id)
    _emit_github_output("count", len(ids))


def cmd_work(args) -> None:
    init_db()
    run_id = args.run_id or _latest_active_run()
    if not run_id:
        logger.info("work: no active run found")
        return
    prog = drive_queue(
        run_id, args.worker_id or _worker_id(), time_budget=args.time_budget,
        request_delay=args.delay, max_pages=args.max_pages, max_depth=args.depth,
        lease_seconds=args.lease,
    )
    print(json.dumps(prog, indent=2))


def cmd_reap(args) -> None:
    init_db()
    if args.all:
        progs = task_queue.reap_all_active()
        print(json.dumps(progs, indent=2))
        return
    run_id = args.run_id or _latest_active_run()
    if not run_id:
        logger.info("reap: no active run found")
        return
    print(json.dumps(task_queue.reap_run(run_id), indent=2))


def cmd_progress(args) -> None:
    run_id = args.run_id or _latest_active_run()
    if not run_id:
        print(json.dumps({"active": False}))
        return
    print(json.dumps(task_queue.run_progress(run_id), indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="MUNI84CR crawler queue CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("enqueue", help="create a run + tasks")
    e.add_argument("--mode", choices=["discover", "monitor"], default="discover")
    e.add_argument("--only-missing", action="store_true")
    e.add_argument("--ids", nargs="*")
    e.add_argument("--max-attempts", type=int, default=3)
    e.set_defaults(func=cmd_enqueue)

    w = sub.add_parser("work", help="process tasks until drained or time budget")
    w.add_argument("--run-id", type=int)
    w.add_argument("--worker-id")
    w.add_argument("--time-budget", type=int, default=3000)
    w.add_argument("--delay", type=float, default=1.0)
    w.add_argument("--max-pages", type=int, default=200)
    w.add_argument("--depth", type=int, default=2)
    w.add_argument("--lease", type=int, default=900)
    w.set_defaults(func=cmd_work)

    r = sub.add_parser("reap", help="requeue/expire/finalize")
    r.add_argument("--run-id", type=int)
    r.add_argument("--all", action="store_true")
    r.set_defaults(func=cmd_reap)

    pr = sub.add_parser("progress", help="print run progress")
    pr.add_argument("--run-id", type=int)
    pr.set_defaults(func=cmd_progress)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
