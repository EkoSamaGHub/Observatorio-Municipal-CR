"""
Crawler queue CLI — wraps the crawler-platform API.

Subcommands:
  enqueue   Submit one crawl job per municipality to the platform (producer).
  work      Poll jobs until complete, then sync results into Observatory DB.
  reap      Report status of all jobs in a job_map; cancel stuck ones.
  progress  Print live status for each job in a job_map as JSON.

Designed so GitHub Actions can run `enqueue` once, then `work` (single job)
to wait for the platform's distributed workers and sync results. The platform
handles all crawl parallelism internally via BullMQ workers.

Env vars:
  PLATFORM_API_URL  Base URL of the crawler-platform API
                    (default: http://localhost:3000)
  DATABASE_URL      Observatory Postgres (leave unset to use local SQLite)
"""

import argparse
import json
import os
import sys

from configs.db import get_connection
from configs.init_db import init_db
from crawlers.crawl_all import load_municipalities
from modules import platform_runner
from modules.logger import logger
from modules.platform_client import PLATFORM_API_URL, CrawlerPlatformClient


# ── helpers ───────────────────────────────────────────────────────────────────

def _emit_github_output(key: str, value: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def _select_muni_ids(mode: str, only_missing: bool, ids: list[str] | None) -> list[str]:
    munis = [m for m in load_municipalities(active_only=True)]

    if ids:
        valid = {m["id"] for m in munis}
        return [i for i in ids if i in valid]

    if mode == "monitor":
        # Only municipalities that already have pages indexed
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT DISTINCT municipality_id FROM pages"
            ).fetchall()
            indexed = {r["municipality_id"] for r in rows}
        finally:
            conn.close()
        return [m["id"] for m in munis if m["id"] in indexed]

    if only_missing:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT DISTINCT municipality_id FROM pages"
            ).fetchall()
            indexed = {r["municipality_id"] for r in rows}
        finally:
            conn.close()
        return [m["id"] for m in munis if m["id"] not in indexed]

    return [m["id"] for m in munis]


def _load_job_map(raw: str) -> dict[str, str]:
    """Parse --job-map argument (JSON string → {muni_id: job_id})."""
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("job_map must be a JSON object")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid --job-map JSON: {e}")
        sys.exit(1)


# ── enqueue ───────────────────────────────────────────────────────────────────

def cmd_enqueue(args) -> None:
    init_db()
    munis = {m["id"]: m for m in load_municipalities(active_only=False)}
    ids = _select_muni_ids(args.mode, only_missing=args.only_missing, ids=args.ids)

    if not ids:
        logger.info("enqueue: no municipalities match — nothing to do")
        _emit_github_output("job_map", "{}")
        _emit_github_output("count", "0")
        return

    with CrawlerPlatformClient() as client:
        if not client.ping():
            logger.error(
                f"Platform API unreachable at {PLATFORM_API_URL} — "
                "is the crawler-platform running?"
            )
            sys.exit(1)
        job_map = platform_runner.submit_jobs(
            client, ids, munis, args.mode, rendering=args.rendering
        )

    job_map_json = json.dumps(job_map)
    print(job_map_json)
    _emit_github_output("job_map", job_map_json)
    _emit_github_output("count", str(len(job_map)))
    logger.info(f"enqueue: {len(job_map)} job(s) submitted")


# ── work ──────────────────────────────────────────────────────────────────────

def cmd_work(args) -> None:
    init_db()
    job_map = _load_job_map(args.job_map)
    if not job_map:
        logger.info("work: empty job_map — nothing to do")
        print(json.dumps({"pages": 0, "documents": 0, "new": 0, "changed": 0, "errors": 0}))
        return

    munis = {m["id"]: m for m in load_municipalities(active_only=False)}
    # Infer mode from the first job name so escalation re-runs use the right seeds.
    mode = "discover"

    with CrawlerPlatformClient() as client:
        logger.info(f"[work] watching {len(job_map)} job(s) (timeout={args.timeout}s)")
        try:
            first = client.get_job(next(iter(job_map.values())))
            parsed = platform_runner.parse_job_name(first.get("name", ""))
            if parsed:
                mode = parsed["mode"]
        except Exception:
            pass

        total = platform_runner.drive_and_sync(
            client, job_map, munis, mode,
            timeout_sec=args.timeout, poll_sec=args.poll_interval,
            auto_retry=not args.no_retry,
        )

    print(json.dumps(total, indent=2))


# ── reap ──────────────────────────────────────────────────────────────────────

def cmd_reap(args) -> None:
    job_map = _load_job_map(args.job_map)
    if not job_map:
        print(json.dumps({}))
        return

    report: dict[str, str] = {}
    with CrawlerPlatformClient() as client:
        for muni_id, job_id in job_map.items():
            try:
                job = client.get_job(job_id)
                status = job.get("status", "UNKNOWN")
                report[muni_id] = status

                if args.cancel_stuck and not client.is_terminal(status):
                    logger.info(f"[reap] cancelling stuck job {job_id} ({muni_id})")
                    client.cancel_job(job_id)
                    report[muni_id] = "CANCELED"
            except Exception as e:
                logger.error(f"[reap] {muni_id} {job_id}: {e}")
                report[muni_id] = "ERROR"

    print(json.dumps(report, indent=2))


# ── progress ──────────────────────────────────────────────────────────────────

def cmd_progress(args) -> None:
    job_map = _load_job_map(args.job_map)
    if not job_map:
        print(json.dumps({}))
        return

    summary: dict[str, dict] = {}
    with CrawlerPlatformClient() as client:
        for muni_id, job_id in job_map.items():
            try:
                job = client.get_job(job_id)
                summary[muni_id] = {
                    "job_id": job_id,
                    "status": job.get("status"),
                    "pages_fetched": job.get("pagesFetched", 0),
                    "pages_extracted": job.get("pagesExtracted", 0),
                    "errors": job.get("errorCount", 0),
                }
            except Exception as e:
                summary[muni_id] = {"job_id": job_id, "status": "ERROR", "error": str(e)}

    print(json.dumps(summary, indent=2))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="MUNI84CR crawler CLI (platform edition)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # enqueue
    e = sub.add_parser("enqueue", help="submit crawl jobs to the platform")
    e.add_argument("--mode", choices=["discover", "monitor"], default="discover")
    e.add_argument("--only-missing", action="store_true",
                   help="discover only municipalities not yet indexed")
    e.add_argument("--ids", nargs="*", metavar="ID",
                   help="specific municipality IDs (default: all active)")
    e.add_argument("--depth", type=int, default=3,
                   help="max crawl depth for discover mode (default 3)")
    e.add_argument("--max-pages", type=int, default=500,
                   help="max pages per municipality for discover mode (default 500)")
    e.add_argument("--rendering", choices=["AUTO", "ALWAYS", "NEVER"], default="AUTO",
                   help="page rendering mode (default AUTO)")
    e.set_defaults(func=cmd_enqueue)

    # work
    w = sub.add_parser("work", help="poll jobs until complete, then sync results")
    w.add_argument("--job-map", required=True,
                   help='JSON string mapping muni_id → job_id from enqueue output')
    w.add_argument("--timeout", type=int, default=7200,
                   help="max seconds to wait for all jobs (default 7200)")
    w.add_argument("--poll-interval", type=int, default=30,
                   help="seconds between status polls (default 30)")
    w.add_argument("--no-retry", action="store_true",
                   help="disable proactive re-run of empty/failed municipalities")
    w.set_defaults(func=cmd_work)

    # reap
    r = sub.add_parser("reap", help="check job statuses; optionally cancel stuck jobs")
    r.add_argument("--job-map", required=True,
                   help='JSON string mapping muni_id → job_id')
    r.add_argument("--cancel-stuck", action="store_true",
                   help="cancel jobs that are not yet in a terminal state")
    r.set_defaults(func=cmd_reap)

    # progress
    pr = sub.add_parser("progress", help="print live job status as JSON")
    pr.add_argument("--job-map", required=True,
                    help='JSON string mapping muni_id → job_id')
    pr.set_defaults(func=cmd_progress)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
