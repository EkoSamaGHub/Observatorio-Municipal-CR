"""
Proactive crawler-platform runner.

One place that knows how to:
  • submit municipality crawl jobs (with muni_id encoded in the job name),
  • classify a finished job's outcome (ok / empty / failed),
  • sync good results into Observatory's DB (protecting historic data),
  • PROACTIVELY re-run empty/failed municipalities once, escalating to full
    page rendering — because a silent "completed but empty" result (a JS-only
    shell or WAF challenge stub) must self-heal, not wait to be noticed.

Used by:
  • crawler_cli.py  (GitHub Actions: submit → drive_and_sync inline)
  • worker.py       (Railway: continuous reconcile loop)
  • admin_ops.py    (admin "Start crawl" / "Re-crawl" submit jobs)

Job-name convention (lets the reconciler map a job back to a municipality and
avoid retrying forever):

    Observatory {Discover|Monitor} [{muni_id}]{ (render)}: {muni_name}

The optional " (render)" tag marks an escalated retry so it is never retried
again.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from configs.db import get_connection
from modules.logger import logger
from modules.platform_client import CrawlerPlatformClient
from modules.platform_sync import sync_job

# Crawl shape per mode
DISCOVER_DEPTH = 3
DISCOVER_MAX_PAGES = 500
MONITOR_DEPTH = 0

# A completed job that extracted this few pages is treated as an empty/stub
# result worth re-running with rendering escalation.
EMPTY_PAGE_THRESHOLD = 1

_NAME_RE = re.compile(r"^Observatory (Discover|Monitor) \[([^\]]+)\]( \(render\))?:")


def _log(fn, msg: str) -> None:
    (fn or logger.info)(msg)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── job naming ─────────────────────────────────────────────────────────────────

def job_name(mode: str, muni_id: str, muni_name: str, rendered: bool = False) -> str:
    tag = " (render)" if rendered else ""
    label = "Monitor" if mode == "monitor" else "Discover"
    return f"Observatory {label} [{muni_id}]{tag}: {muni_name}"


def parse_job_name(name: str) -> dict | None:
    """Return {'mode','muni_id','is_retry'} for an Observatory job name, else None."""
    m = _NAME_RE.match(name or "")
    if not m:
        return None
    return {
        "mode": "monitor" if m.group(1) == "Monitor" else "discover",
        "muni_id": m.group(2),
        "is_retry": bool(m.group(3)),
    }


# ── outcome classification ─────────────────────────────────────────────────────

def _stats(job: dict) -> dict:
    # Detail endpoint nests under "stats"; list endpoint is flat.
    return job.get("stats") or {
        "pagesExtracted": job.get("pagesExtracted", 0),
        "pagesFetched": job.get("pagesFetched", 0),
        "errors": job.get("errorCount", 0),
    }


def classify_outcome(job: dict) -> str:
    """'ok' | 'empty' | 'failed' for a (usually completed) job."""
    status = (job.get("status") or "").upper()
    if status in ("FAILED", "CANCELED"):
        return "failed"
    s = _stats(job)
    extracted = s.get("pagesExtracted", 0) or 0
    errors = s.get("errors", 0) or 0
    if extracted == 0 and errors > 0:
        return "failed"
    if extracted <= EMPTY_PAGE_THRESHOLD:
        return "empty"   # stub / JS-only / WAF challenge page
    return "ok"


# ── submission ─────────────────────────────────────────────────────────────────

def _job_params(muni: dict, mode: str, conn) -> dict | None:
    """Seeds + limits for a municipality. None if monitor with nothing indexed."""
    if mode == "monitor":
        rows = conn.execute(
            "SELECT url FROM pages WHERE municipality_id = %s", (muni["id"],)
        ).fetchall()
        seeds = [r["url"] for r in rows]
        if not seeds:
            return None
        return {"seeds": seeds, "max_depth": MONITOR_DEPTH, "max_pages": len(seeds) + 50}
    return {"seeds": [muni["root_url"]], "max_depth": DISCOVER_DEPTH, "max_pages": DISCOVER_MAX_PAGES}


def submit_jobs(client: CrawlerPlatformClient, muni_ids: list[str],
                munis_lookup: dict[str, dict], mode: str,
                rendering: str = "AUTO", rendered_tag: bool = False,
                log=None) -> dict[str, str]:
    """Submit one job per municipality. Returns {muni_id: job_id}."""
    job_map: dict[str, str] = {}
    conn = get_connection() if mode == "monitor" else None
    try:
        for muni_id in muni_ids:
            muni = munis_lookup.get(muni_id)
            if not muni:
                continue
            params = _job_params(muni, mode, conn) if conn else _job_params(muni, mode, None)
            if params is None:
                _log(log, f"[runner] {muni_id}: nothing to {mode}, skipping")
                continue
            try:
                job = client.create_job(
                    name=job_name(mode, muni_id, muni["name"], rendered=rendered_tag),
                    rendering_mode=rendering,
                    **params,
                )
                job_map[muni_id] = job["id"]
                _log(log, f"[runner] submitted {muni_id} -> {job['id']}"
                          f"{' (render)' if rendered_tag else ''}")
            except Exception as e:
                _log(log, f"[runner] submit {muni_id} failed: {e}")
    finally:
        if conn:
            conn.close()
    return job_map


# ── sync (with historic-data protection) ───────────────────────────────────────

def _indexed_count(conn, muni_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM pages WHERE municipality_id = %s", (muni_id,)
    ).fetchone()
    return int(row["n"]) if row else 0


def sync_one(client: CrawlerPlatformClient, muni_id: str, muni: dict,
             job_id: str, outcome: str, log=None) -> dict:
    """Pull a job's pages and upsert into Observatory.

    Protects historic data: refuses to overwrite an already-populated
    municipality with a near-empty (stub) re-crawl.
    """
    pages = client.list_pages(job_id)
    conn = get_connection()
    try:
        if outcome != "ok" and len(pages) <= EMPTY_PAGE_THRESHOLD and _indexed_count(conn, muni_id) > EMPTY_PAGE_THRESHOLD:
            _log(log, f"[runner] {muni_id}: empty re-crawl ({len(pages)} pages) — "
                      f"keeping existing index, not overwriting")
            return {"pages": 0, "documents": 0, "new": 0, "changed": 0,
                    "errors": 0, "skipped": True}
        stats = sync_job(job_id, muni_id, muni["root_url"], pages, conn)
        stats["skipped"] = False
        return stats
    finally:
        conn.close()


# ── handled-job bookkeeping (reconcile loop) ────────────────────────────────────

def is_handled(conn, job_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM platform_jobs WHERE job_id = %s", (job_id,)
    ).fetchone() is not None


def mark_handled(conn, job_id: str, muni_id: str, mode: str, outcome: str,
                 retried_as: str | None = None, pages: int = 0) -> None:
    conn.execute(
        "INSERT INTO platform_jobs (job_id, municipality_id, mode, outcome, "
        "retried_as, pages_synced, handled_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (job_id) DO UPDATE SET outcome=EXCLUDED.outcome, "
        "retried_as=EXCLUDED.retried_as, pages_synced=EXCLUDED.pages_synced, "
        "handled_at=EXCLUDED.handled_at",
        (job_id, muni_id, mode, outcome, retried_as, pages, _now_iso()),
    )
    conn.commit()


# ── inline driver (GitHub Actions: known job_map, ephemeral) ────────────────────

def drive_and_sync(client: CrawlerPlatformClient, job_map: dict[str, str],
                   munis_lookup: dict[str, dict], mode: str,
                   timeout_sec: int = 7200, poll_sec: int = 30,
                   auto_retry: bool = True, log=None) -> dict:
    """Wait for jobs, sync results, then re-run empty/failed munis once with
    rendering=ALWAYS and wait+sync those too. Returns aggregate stats."""
    totals = {"pages": 0, "documents": 0, "new": 0, "changed": 0,
              "errors": 0, "retried": 0, "synced": 0}

    def _accumulate(stats: dict) -> None:
        for k in ("pages", "documents", "new", "changed", "errors"):
            totals[k] += stats.get(k, 0)
        if not stats.get("skipped"):
            totals["synced"] += 1

    def _process(jmap: dict[str, str], allow_retry: bool) -> list[str]:
        results = client.wait_for_all(list(jmap.values()),
                                      poll_sec=poll_sec, timeout_sec=timeout_sec)
        retry_ids: list[str] = []
        for muni_id, job_id in jmap.items():
            job = results.get(job_id, {})
            outcome = classify_outcome(job)
            muni = munis_lookup.get(muni_id)
            if not muni:
                continue
            if outcome in ("empty", "failed") and allow_retry:
                _log(log, f"[runner] {muni_id}: {outcome} -> re-running with rendering=ALWAYS")
                retry_ids.append(muni_id)
                totals["errors"] += 1   # counts until the retry succeeds
                continue
            try:
                stats = sync_one(client, muni_id, muni, job_id, outcome, log=log)
                _accumulate(stats)
                _log(log, f"[runner] {muni_id} [{outcome}]: pages={stats['pages']} "
                          f"new={stats['new']} changed={stats['changed']} "
                          f"docs={stats['documents']}"
                          f"{' (kept existing)' if stats.get('skipped') else ''}")
            except Exception as e:
                _log(log, f"[runner] sync {muni_id} failed: {e}")
                totals["errors"] += 1
        return retry_ids

    retry_ids = _process(job_map, allow_retry=auto_retry)

    if retry_ids:
        retry_map = submit_jobs(client, retry_ids, munis_lookup, mode,
                                rendering="ALWAYS", rendered_tag=True, log=log)
        totals["retried"] = len(retry_map)
        if retry_map:
            # Escalated round no longer counts as pre-emptive errors.
            totals["errors"] = max(0, totals["errors"] - len(retry_map))
            _process(retry_map, allow_retry=False)

    return totals


# ── reconcile (Railway worker: continuous, covers admin-started jobs) ───────────

def reconcile(client: CrawlerPlatformClient, munis_lookup: dict[str, dict],
              auto_retry: bool = True, limit: int = 100, log=None) -> dict:
    """Scan the platform for completed Observatory jobs we haven't handled yet.
    Sync good ones; proactively re-run empty/failed ones (once, escalated).

    This is what makes admin-started and worker-started crawls self-heal without
    anyone waiting on them."""
    summary = {"checked": 0, "synced": 0, "retried": 0, "skipped": 0, "errors": 0}
    try:
        r = client._session.get(f"{client._base}/v1/crawls",
                                params={"limit": limit}, timeout=10)
        r.raise_for_status()
        jobs = r.json().get("items", [])
    except Exception as e:
        _log(log, f"[reconcile] could not list jobs: {e}")
        return summary

    conn = get_connection()
    try:
        for job in jobs:
            if (job.get("status") or "").upper() != "COMPLETED":
                continue
            parsed = parse_job_name(job.get("name", ""))
            if not parsed:
                continue
            job_id = job["id"]
            if is_handled(conn, job_id):
                continue

            summary["checked"] += 1
            muni_id = parsed["muni_id"]
            muni = munis_lookup.get(muni_id)
            if not muni:
                mark_handled(conn, job_id, muni_id, parsed["mode"], "unknown_muni")
                continue

            outcome = classify_outcome(job)

            # First-time empty/failed (not already a render retry) → escalate.
            if outcome in ("empty", "failed") and auto_retry and not parsed["is_retry"]:
                retry_map = submit_jobs(client, [muni_id], munis_lookup,
                                        parsed["mode"], rendering="ALWAYS",
                                        rendered_tag=True, log=log)
                new_id = retry_map.get(muni_id)
                mark_handled(conn, job_id, muni_id, parsed["mode"], outcome,
                             retried_as=new_id)
                summary["retried"] += 1
                _log(log, f"[reconcile] {muni_id}: {outcome} -> escalated to {new_id}")
                continue

            # ok, or an already-escalated retry → sync and accept.
            try:
                stats = sync_one(client, muni_id, muni, job_id, outcome, log=log)
                mark_handled(conn, job_id, muni_id, parsed["mode"], outcome,
                             pages=stats.get("pages", 0))
                if stats.get("skipped"):
                    summary["skipped"] += 1
                else:
                    summary["synced"] += 1
            except Exception as e:
                _log(log, f"[reconcile] sync {muni_id} failed: {e}")
                summary["errors"] += 1
    finally:
        conn.close()

    return summary
