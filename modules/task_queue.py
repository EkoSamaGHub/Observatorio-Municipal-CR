"""
Lease-based crawl task queue.

A run is a batch of per-municipality tasks. Workers atomically *claim* a task
(taking a time-bounded lease), send heartbeats while working, then mark it
done/failed. If a worker dies, its lease expires and the task is re-claimable —
this is what makes the system recoverable across crashes and redeploys.

Concurrency model:
  - Postgres: SELECT ... FOR UPDATE SKIP LOCKED → many workers claim in
    parallel without blocking or double-processing. No deadlocks.
  - SQLite: single-writer dev fallback (no SKIP LOCKED needed).

Task status:  pending → running → done | failed | dead
  - failed: attempts remain, will be retried
  - dead:   exhausted max_attempts, abandoned (stops retry storms)
"""

from datetime import datetime, timedelta, timezone

from configs.db import BACKEND, get_connection
from modules import events

TERMINAL = ("done", "dead")
# A run in one of these states must not hand out tasks; workers polling
# claim_task() get None and idle/stop. This is how admin pause/stop/cancel
# halts the distributed workers without any infrastructure access.
HALTED_STATES = ("paused", "stopped", "cancelled")
DEFAULT_LEASE_SECONDS = 600  # 10 min — must exceed the slowest single-muni crawl
# A run with no heartbeat for this long is treated as abandoned: any tasks
# still 'pending' on it are marked dead so the run can finalize instead of
# staying "running" forever. Set well above the lease window so that a worker
# briefly pausing between claims (CF stealth fetches can take >60 s) never
# triggers premature abandonment.
STALE_RUN_MINUTES = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _now_iso() -> str:
    return _iso(_now())


# ── Run + task creation ────────────────────────────────────────────────────────

def create_run(municipality_ids: list[str], mode: str, worker_id: str = "",
               max_attempts: int = 3) -> int:
    """Create a run and one pending task per municipality. Returns run_id."""
    now = _now_iso()
    conn = get_connection()
    try:
        run_id = conn.execute(
            "INSERT INTO crawl_runs (started_at, status, mode, worker_id, last_heartbeat) "
            "VALUES (%s, 'running', %s, %s, %s) RETURNING id",
            (now, mode, worker_id, now),
        ).lastrowid
        for mid in municipality_ids:
            conn.execute(
                "INSERT INTO crawl_tasks "
                "(run_id, municipality_id, mode, status, max_attempts, created_at, updated_at) "
                "VALUES (%s, %s, %s, 'pending', %s, %s, %s)",
                (run_id, mid, mode, max_attempts, now, now),
            )
        conn.commit()
        events.log_event(
            "run_started", run_id=int(run_id),
            message=f"Run {run_id} enqueued: {len(municipality_ids)} municipalities (mode={mode})",
            meta={"mode": mode, "count": len(municipality_ids), "worker_id": worker_id},
            conn=conn,
        )
        return int(run_id)
    finally:
        conn.close()


# ── Claiming ────────────────────────────────────────────────────────────────────

def claim_task(run_id: int, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> dict | None:
    """Atomically claim the next workable task for `run_id`, or None if none left.

    Workable = pending, OR running with an expired lease (a dead worker's task),
    in both cases with attempts still below max_attempts.
    """
    now = _now()
    now_iso = _iso(now)
    lease_until = _iso(now + timedelta(seconds=lease_seconds))

    conn = get_connection()
    try:
        # Respect operator control: a paused/stopped/cancelled run yields no
        # work, so every worker on it winds down on its next poll.
        run = conn.execute(
            "SELECT status FROM crawl_runs WHERE id=%s", (run_id,)
        ).fetchone()
        if run and run.get("status") in HALTED_STATES:
            conn.commit()
            return None

        select_sql = (
            "SELECT id FROM crawl_tasks "
            "WHERE run_id = %s "
            "  AND attempts < max_attempts "
            "  AND (status = 'pending' OR (status IN ('running','failed') AND "
            "       (lease_expires_at IS NULL OR lease_expires_at < %s))) "
            "ORDER BY id LIMIT 1"
        )
        if BACKEND == "postgres":
            select_sql += " FOR UPDATE SKIP LOCKED"

        row = conn.execute(select_sql, (run_id, now_iso)).fetchone()
        if not row:
            conn.commit()  # release any FOR UPDATE locks / end txn
            return None

        task_id = row["id"]
        conn.execute(
            "UPDATE crawl_tasks "
            "SET status='running', leased_by=%s, lease_expires_at=%s, heartbeat=%s, "
            "    attempts = attempts + 1, updated_at=%s "
            "WHERE id=%s",
            (worker_id, lease_until, now_iso, now_iso, task_id),
        )
        conn.commit()

        return conn.execute(
            "SELECT * FROM crawl_tasks WHERE id=%s", (task_id,)
        ).fetchone()
    finally:
        conn.close()


# ── Heartbeat / completion ───────────────────────────────────────────────────────

def heartbeat(task_id: int, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS,
              pages_found: int | None = None) -> None:
    """Extend a task's lease while it is still being worked on."""
    now = _now()
    now_iso = _iso(now)
    lease_until = _iso(now + timedelta(seconds=lease_seconds))
    conn = get_connection()
    try:
        if pages_found is None:
            conn.execute(
                "UPDATE crawl_tasks SET lease_expires_at=%s, heartbeat=%s, updated_at=%s "
                "WHERE id=%s AND leased_by=%s",
                (lease_until, now_iso, now_iso, task_id, worker_id),
            )
        else:
            conn.execute(
                "UPDATE crawl_tasks SET lease_expires_at=%s, heartbeat=%s, updated_at=%s, pages_found=%s "
                "WHERE id=%s AND leased_by=%s",
                (lease_until, now_iso, now_iso, pages_found, task_id, worker_id),
            )
        conn.execute(
            "UPDATE crawl_runs SET last_heartbeat=%s WHERE id="
            "(SELECT run_id FROM crawl_tasks WHERE id=%s)",
            (now_iso, task_id),
        )
        conn.commit()
    finally:
        conn.close()


def complete_task(task_id: int, pages_found: int = 0, sitemap_total: int = 0,
                  completeness_pct: float = 0.0) -> None:
    now = _now_iso()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE crawl_tasks SET status='done', pages_found=%s, sitemap_total=%s, "
            "completeness_pct=%s, error=NULL, lease_expires_at=NULL, updated_at=%s WHERE id=%s",
            (pages_found, sitemap_total, completeness_pct, now, task_id),
        )
        row = conn.execute(
            "SELECT run_id, municipality_id FROM crawl_tasks WHERE id=%s", (task_id,)
        ).fetchone()
        conn.commit()
        if row:
            events.log_event(
                "muni_completed", run_id=row["run_id"], task_id=task_id,
                municipality_id=row["municipality_id"],
                message=f"{row['municipality_id']}: {pages_found} pages indexed",
                meta={"pages": pages_found, "completeness_pct": completeness_pct},
                conn=conn,
            )
    finally:
        conn.close()


def fail_task(task_id: int, error: str) -> None:
    """Record a failure. Becomes 'dead' once attempts are exhausted, otherwise
    'failed' (re-claimable for retry). attempts was already incremented on claim."""
    now = _now_iso()
    conn = get_connection()
    try:
        task = conn.execute(
            "SELECT attempts, max_attempts FROM crawl_tasks WHERE id=%s", (task_id,)
        ).fetchone()
        status = "dead" if task and task["attempts"] >= task["max_attempts"] else "failed"
        conn.execute(
            "UPDATE crawl_tasks SET status=%s, error=%s, lease_expires_at=NULL, updated_at=%s WHERE id=%s",
            (status, (error or "")[:500], now, task_id),
        )
        row = conn.execute(
            "SELECT run_id, municipality_id FROM crawl_tasks WHERE id=%s", (task_id,)
        ).fetchone()
        conn.commit()
        if row:
            events.log_event(
                "muni_dead" if status == "dead" else "muni_failed",
                level="error" if status == "dead" else "warn",
                run_id=row["run_id"], task_id=task_id,
                municipality_id=row["municipality_id"],
                message=f"{row['municipality_id']} {status}: {error}",
                conn=conn,
            )
    finally:
        conn.close()


# ── Reaping / finalization ───────────────────────────────────────────────────────

def reap_run(run_id: int) -> dict:
    """Requeue tasks whose lease expired (crashed workers) and mark exhausted
    ones dead. Finalize the run if every task is terminal. Returns progress.

    If the run has had no heartbeat for STALE_RUN_MINUTES, any tasks still
    'pending' are also marked dead — they were never claimed by any worker
    (e.g. GHA workers timed out before reaching the tail of the queue), and
    without this the run stays "running" indefinitely and the next nightly
    enqueue creates a parallel run that orphans these forever.
    """
    now_dt = _now()
    now = _iso(now_dt)
    conn = get_connection()
    try:
        # Exhausted + expired → dead (stops retry storms against broken sites).
        conn.execute(
            "UPDATE crawl_tasks SET status='dead', lease_expires_at=NULL, updated_at=%s "
            "WHERE run_id=%s AND status IN ('running','failed') "
            "  AND attempts >= max_attempts "
            "  AND (lease_expires_at IS NULL OR lease_expires_at < %s)",
            (now, run_id, now),
        )
        # Still has attempts + expired → back to pending for retry.
        conn.execute(
            "UPDATE crawl_tasks SET status='pending', leased_by=NULL, lease_expires_at=NULL, updated_at=%s "
            "WHERE run_id=%s AND status IN ('running','failed') "
            "  AND attempts < max_attempts "
            "  AND lease_expires_at IS NOT NULL AND lease_expires_at < %s",
            (now, run_id, now),
        )
        conn.commit()

        # Stale-pending sweep: if no worker has heartbeat'd in a while, mark
        # unclaimed pending tasks dead so _finalize_run can close the run.
        # The next discover/only-missing enqueue will create fresh tasks for
        # any munis these covered (only_missing checks pages table, not tasks).
        run_row = conn.execute(
            "SELECT started_at, last_heartbeat FROM crawl_runs WHERE id=%s",
            (run_id,),
        ).fetchone()
        if run_row:
            ref = run_row.get("last_heartbeat") or run_row.get("started_at")
            if ref and _is_older_than(ref, now_dt, STALE_RUN_MINUTES):
                conn.execute(
                    "UPDATE crawl_tasks SET status='dead', error=%s, "
                    "lease_expires_at=NULL, updated_at=%s "
                    "WHERE run_id=%s AND status='pending'",
                    ("unclaimed: run abandoned (no heartbeat)", now, run_id),
                )
                conn.commit()
    finally:
        conn.close()

    prog = run_progress(run_id)
    if prog["pending"] == 0 and prog["running"] == 0 and prog["total"] > 0:
        _finalize_run(run_id, prog)
        prog = run_progress(run_id)
    return prog


def _is_older_than(ts, now_dt: datetime, minutes: int) -> bool:
    """True if `ts` (ISO-8601 string or datetime) predates now_dt by more than
    `minutes`. Unparseable values are treated as old to avoid pinning a run
    open on bad data."""
    if ts is None:
        return True
    if isinstance(ts, datetime):
        parsed = ts
    else:
        try:
            parsed = datetime.fromisoformat(str(ts))
        except ValueError:
            return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (now_dt - parsed) > timedelta(minutes=minutes)


def reap_all_active() -> list[dict]:
    """Reap every run that is still marked running. Used by the background reaper."""
    conn = get_connection()
    try:
        # Only reap genuinely-running runs. Paused/stopped/cancelled runs are
        # held intentionally and must not be requeued or finalized by the reaper.
        rows = conn.execute(
            "SELECT id FROM crawl_runs WHERE status='running'"
        ).fetchall()
    finally:
        conn.close()
    return [reap_run(r["id"]) for r in rows]


def _finalize_run(run_id: int, prog: dict) -> None:
    now = _now_iso()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE crawl_runs SET finished_at=%s, status='done', "
            "municipalities=%s, pages_crawled=%s, errors=%s, sitemap_urls_found=%s "
            "WHERE id=%s AND finished_at IS NULL",
            (now, prog["total"], prog["pages"], prog["dead"] + prog["failed"],
             prog["sitemap_total"], run_id),
        )
        conn.commit()
        events.log_event(
            "run_finished", run_id=run_id,
            level="error" if prog["dead"] else "info",
            message=f"Run {run_id} finished: {prog['done']} done, {prog['dead']} dead, {prog['pages']} pages",
            meta={"done": prog["done"], "dead": prog["dead"], "failed": prog["failed"],
                  "pages": prog["pages"]},
            conn=conn,
        )
    finally:
        conn.close()


# ── Progress ─────────────────────────────────────────────────────────────────────

def run_progress(run_id: int) -> dict:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n, COALESCE(SUM(pages_found),0) AS pages, "
            "COALESCE(SUM(sitemap_total),0) AS sitemap FROM crawl_tasks "
            "WHERE run_id=%s GROUP BY status",
            (run_id,),
        ).fetchall()
        hb = conn.execute(
            "SELECT MAX(heartbeat) AS ts FROM crawl_tasks WHERE run_id=%s", (run_id,)
        ).fetchone()
        current = conn.execute(
            "SELECT municipality_id FROM crawl_tasks WHERE run_id=%s AND status='running' "
            "ORDER BY heartbeat DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()

    by = {r["status"]: r for r in rows}
    counts = {s: int(by.get(s, {}).get("n", 0)) for s in
              ("pending", "running", "done", "failed", "dead", "skipped")}
    total = sum(counts.values())
    terminal = counts["done"] + counts["dead"] + counts["skipped"]
    return {
        "run_id": run_id,
        "total": total,
        "pending": counts["pending"],
        "running": counts["running"],
        "done": counts["done"],
        "failed": counts["failed"],
        "dead": counts["dead"],
        "skipped": counts["skipped"],
        "terminal": terminal,
        "pages": int(sum(r["pages"] for r in rows)),
        "sitemap_total": int(sum(r["sitemap"] for r in rows)),
        "last_heartbeat": hb["ts"] if hb else None,
        "current_municipality": current["municipality_id"] if current else None,
        "pct": round(terminal / total * 100, 1) if total else 0.0,
    }
