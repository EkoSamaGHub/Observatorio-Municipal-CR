"""
Admin control-plane operations.

This is the brain behind the admin dashboard. It does NOT crawl — the API
process is a web server, and running multi-hour crawls in-process is what
previously exhausted the Postgres connection pool and took the site down.
Instead every action mutates the durable queue state in `crawl_runs` /
`crawl_tasks` that the existing distributed workers (GitHub Actions + the
Railway `worker.py` reaper/monitor) already obey. Starting real crawl capacity
on demand is done by dispatching the GitHub Actions workflow (token-gated).

Kept intentionally dependency-light (db + stdlib + task_queue/events only) so
importing it never drags the scrapling/crawler stack into the API process.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from configs.db import BACKEND, get_connection
from modules import events, platform_runner, task_queue
from modules.platform_client import CrawlerPlatformClient, PLATFORM_API_URL

MUNICIPALITIES_FILE = Path("municipalities.json")

# Liveness window: a "running" run whose newest heartbeat is older than this has
# no live worker. Matches the proxy used by the public /runs/active endpoint.
STALE_MINUTES = 20


# ── time helpers ──────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _age_minutes(ts) -> float | None:
    dt = _parse(ts)
    if dt is None:
        return None
    return (_now() - dt).total_seconds() / 60.0


def _is_stale(ts) -> bool:
    age = _age_minutes(ts)
    return age is None or age > STALE_MINUTES


def _duration_seconds(start, end) -> float | None:
    s, e = _parse(start), _parse(end or _now_iso())
    if s is None or e is None:
        return None
    return max(0.0, (e - s).total_seconds())


# ── registry ────────────────────────────────────────────────────────────────

def _load_registry() -> list[dict]:
    try:
        with open(MUNICIPALITIES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _registry_map() -> dict[str, dict]:
    return {m["id"]: m for m in _load_registry()}


def _select_ids(mode: str, only_missing: bool, ids: list[str] | None) -> list[str]:
    """Resolve the municipality IDs a run should cover. Mirrors
    pipeline.select_municipality_ids without importing the crawler stack."""
    munis = [m for m in _load_registry() if m.get("active", True)]
    if ids:
        munis = [m for m in munis if m["id"] in ids]
    if mode == "monitor" or only_missing:
        conn = get_connection()
        try:
            indexed = {
                r["municipality_id"]
                for r in conn.execute(
                    "SELECT DISTINCT municipality_id FROM pages"
                ).fetchall()
            }
        finally:
            conn.close()
        if mode == "monitor":
            munis = [m for m in munis if m["id"] in indexed]
        elif only_missing:
            munis = [m for m in munis if m["id"] not in indexed]
    return [m["id"] for m in munis]


# ── run classification / liveness ─────────────────────────────────────────────

def classify_run(run: dict, prog: dict | None) -> str:
    """Derive the operational state from raw run + task progress.

    active   — running, worker heartbeat fresh
    stale    — running, heartbeat expired (worker likely dead, recoverable)
    orphaned — running, no tasks and never finalized (legacy zombie)
    paused/stopped/cancelled/done — explicit terminal/held states
    """
    status = (run.get("status") or "running").lower()
    if status in ("paused", "stopped", "cancelled"):
        return status
    if run.get("finished_at") or status == "done":
        return "done"

    # status == running (or legacy NULL)
    has_tasks = bool(prog and prog.get("total"))
    if not has_tasks:
        return "orphaned" if _is_stale(run.get("started_at")) else "active"
    hb = prog.get("last_heartbeat") or run.get("last_heartbeat") or run.get("started_at")
    return "active" if not _is_stale(hb) else "stale"


def _run_row(run_id: int) -> dict | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM crawl_runs WHERE id=%s", (run_id,)
        ).fetchone()
    finally:
        conn.close()


def _enrich_run(run: dict) -> dict:
    prog = task_queue.run_progress(run["id"])
    state = classify_run(run, prog)
    hb = prog.get("last_heartbeat") or run.get("last_heartbeat")
    duration = _duration_seconds(run.get("started_at"), run.get("finished_at"))
    speed = None
    if duration and duration > 0 and prog.get("pages"):
        speed = round(prog["pages"] / (duration / 60.0), 1)  # pages/min
    return {
        "id": run["id"],
        "status": run.get("status"),
        "state": state,
        "mode": run.get("mode"),
        "worker_id": run.get("worker_id"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "last_heartbeat": hb,
        "heartbeat_age_min": round(_age_minutes(hb), 1) if _age_minutes(hb) is not None else None,
        "duration_seconds": round(duration) if duration is not None else None,
        "pages_per_min": speed,
        "progress": prog,
    }


def list_runs(limit: int = 25) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM crawl_runs ORDER BY started_at DESC LIMIT %s", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return [_enrich_run(r) for r in rows]


# ── worker observability ──────────────────────────────────────────────────────

def workers() -> list[dict]:
    """Live workers inferred from currently-leased tasks."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT leased_by, COUNT(*) AS tasks, MAX(heartbeat) AS last_heartbeat, "
            "MAX(lease_expires_at) AS lease_expires_at "
            "FROM crawl_tasks WHERE status='running' AND leased_by IS NOT NULL "
            "GROUP BY leased_by"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        age = _age_minutes(r["last_heartbeat"])
        out.append({
            "worker_id": r["leased_by"],
            "active_tasks": r["tasks"],
            "last_heartbeat": r["last_heartbeat"],
            "heartbeat_age_min": round(age, 1) if age is not None else None,
            "alive": not _is_stale(r["last_heartbeat"]),
        })
    return out


# ── platform integration ──────────────────────────────────────────────────────

def platform_jobs(limit: int = 20) -> list[dict]:
    """Recent crawler-platform jobs, newest first. Returns [] if unreachable."""
    try:
        with CrawlerPlatformClient() as c:
            r = c._session.get(
                f"{c._base}/v1/crawls",
                params={"limit": limit},
                timeout=5,
            )
            r.raise_for_status()
            return r.json().get("items", [])
    except Exception:
        return []


def platform_active_jobs() -> list[dict]:
    return [j for j in platform_jobs(limit=10)
            if j.get("status") in ("RUNNING", "QUEUED", "DRAINING")]


def cancel_platform_job(job_id: str) -> dict:
    try:
        with CrawlerPlatformClient() as c:
            c.cancel_job(job_id)
        return {"ok": True, "job_id": job_id}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def platform_job_detail(job_id: str) -> dict:
    """Full job detail — stats + per-task status breakdown — for the admin
    drill-down. Returns {"ok": False, ...} if the platform is unreachable."""
    try:
        with CrawlerPlatformClient() as c:
            job = c.get_job(job_id)
        return {"ok": True, **job}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def platform_job_errors(job_id: str, limit: int = 50) -> dict:
    """Recorded crawl errors for a job (stage / code / message / timestamp).

    This is the 'why did it fail' view the admin dashboard needs. A job can be
    COMPLETED yet still have terminal task errors (e.g. SSRF / TOO_LARGE), so
    this is surfaced independently of job status."""
    try:
        with CrawlerPlatformClient() as c:
            errors = c.list_errors(job_id, limit=limit)
        # Group by code for a quick at-a-glance summary
        by_code: dict[str, int] = {}
        for e in errors:
            code = e.get("code") or "UNKNOWN"
            by_code[code] = by_code.get(code, 0) + 1
        return {"ok": True, "count": len(errors), "by_code": by_code, "errors": errors}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "errors": []}


# ── dashboard overview ────────────────────────────────────────────────────────

def overview() -> dict:
    conn = get_connection()
    try:
        runs = conn.execute(
            "SELECT * FROM crawl_runs ORDER BY started_at DESC LIMIT 50"
        ).fetchall()
        indexed = conn.execute(
            "SELECT COUNT(DISTINCT municipality_id) AS n FROM pages"
        ).fetchone()["n"]
        total_pages = conn.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]
        total_docs = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
        db_ok = True
    except Exception:
        runs, indexed, total_pages, total_docs, db_ok = [], 0, 0, 0, False
    finally:
        conn.close()

    registry = _load_registry()
    total_munis = len([m for m in registry if m.get("active", True)]) or 84

    enriched = [_enrich_run(r) for r in runs]
    by_state: dict[str, int] = {}
    for r in enriched:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1

    # Prefer a live crawler-platform job; fall back to a live legacy run.
    active = active_running_run() or next(
        (r for r in enriched if r["state"] in ("active", "stale")), None
    )
    last_success = next(
        (r for r in enriched if r["state"] == "done" and r["progress"]["dead"] == 0
         and r["progress"]["done"] > 0),
        None,
    )
    last_failed = next(
        (r for r in enriched if r["progress"]["dead"] > 0 or r["progress"]["failed"] > 0),
        None,
    )

    live_workers = workers()

    # Platform status (non-blocking — failure just shows ok=False)
    try:
        pjobs = platform_jobs(limit=20)
        p_active = [j for j in pjobs if j.get("status") in ("RUNNING", "QUEUED", "DRAINING")]
        p_recent = [j for j in pjobs if j.get("status") in ("COMPLETED", "FAILED", "CANCELED")][:5]
        platform_info: dict = {
            "ok": True,
            "url": PLATFORM_API_URL,
            "active_count": len(p_active),
            "active_jobs": p_active,
            "recent_jobs": p_recent,
        }
    except Exception as e:
        platform_info = {"ok": False, "url": PLATFORM_API_URL, "error": str(e)[:200]}

    return {
        "generated_at": _now_iso(),
        "system": {
            "db_ok": db_ok,
            "backend": BACKEND,
            "stale_minutes": STALE_MINUTES,
            "dispatch_configured": bool(os.environ.get("GH_DISPATCH_TOKEN") and os.environ.get("GH_REPO")),
            "platform_url": PLATFORM_API_URL,
            "environment": _env_metadata(),
        },
        "coverage": {
            "municipalities_indexed": indexed,
            "municipalities_total": total_munis,
            "coverage_pct": round(indexed / total_munis * 100, 1) if total_munis else 0.0,
            "total_pages": total_pages,
            "total_documents": total_docs,
        },
        "runs_by_state": by_state,
        "active_run": active,
        "last_success": last_success,
        "last_failed": last_failed,
        "workers": {
            "count": len(live_workers),
            "alive": sum(1 for w in live_workers if w["alive"]),
            "list": live_workers,
        },
        "platform": platform_info,
    }


def _env_metadata() -> dict:
    """Non-secret deployment metadata (never the DATABASE_URL)."""
    keys = [
        "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_SERVICE_NAME",
        "RAILWAY_PROJECT_NAME", "RAILWAY_REPLICA_ID", "RAILWAY_REGION",
        "RAILWAY_GIT_COMMIT_SHA", "RAILWAY_GIT_BRANCH", "GH_REPO",
    ]
    meta = {k: os.environ[k] for k in keys if os.environ.get(k)}
    meta["worker_mode"] = bool(os.environ.get("WORKER_MODE"))
    return meta


# ── per-municipality task detail ──────────────────────────────────────────────

def run_tasks(run_id: int) -> list[dict]:
    reg = _registry_map()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM crawl_tasks WHERE run_id=%s ORDER BY municipality_id", (run_id,)
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        m = reg.get(r["municipality_id"], {})
        lease_expired = _is_stale(r.get("lease_expires_at")) if r.get("status") == "running" else False
        out.append({
            **r,
            "name": m.get("name"),
            "province": m.get("province"),
            "duration_seconds": _duration_seconds(r.get("created_at"), r.get("updated_at")),
            "heartbeat_age_min": (
                round(_age_minutes(r.get("heartbeat")), 1)
                if _age_minutes(r.get("heartbeat")) is not None else None
            ),
            "lease_expired": lease_expired,
        })
    return out


# ── control: start / dispatch ─────────────────────────────────────────────────

def active_running_run() -> dict | None:
    """The single live run, if any.

    Checks the crawler-platform first (new crawls), then falls back to the
    legacy crawl_runs table (historical / in-flight legacy runs).
    """
    p_active = platform_active_jobs()
    if p_active:
        j = p_active[0]
        # The list endpoint omits discovered/extracted; fetch the detail of the
        # single active job so the progress bar reflects real numbers.
        try:
            with CrawlerPlatformClient() as c:
                j = c.get_job(j["id"]) or j
        except Exception:
            pass
        stats = j.get("stats", {})
        discovered = stats.get("pagesDiscovered", 0) or 1
        extracted = stats.get("pagesExtracted", 0)
        pct = round(extracted / discovered * 100, 1) if discovered else 0.0
        return {
            "source": "platform",
            "id": j.get("id"),
            "status": j.get("status", "").lower(),
            "state": "active",
            "mode": "monitor" if "monitor" in (j.get("name") or "").lower() else "discover",
            "started_at": j.get("startedAt"),
            "finished_at": j.get("completedAt"),
            "last_heartbeat": j.get("updatedAt"),
            "heartbeat_age_min": None,
            "duration_seconds": None,
            "pages_per_min": None,
            "progress": {
                "run_id": j.get("id"),
                "total": discovered,
                "pending": stats.get("pagesDiscovered", 0) - extracted,
                "running": 0,
                "done": extracted,
                "failed": stats.get("errors", 0),
                "dead": 0,
                "skipped": 0,
                "terminal": extracted,
                "pages": extracted,
                "sitemap_total": 0,
                "last_heartbeat": None,
                "current_municipality": None,
                "pct": pct,
            },
        }

    # Fall back to legacy crawl_runs
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM crawl_runs WHERE status='running' ORDER BY started_at DESC"
        ).fetchall()
    finally:
        conn.close()
    for r in rows:
        prog = task_queue.run_progress(r["id"])
        if classify_run(r, prog) in ("active", "stale"):
            return _enrich_run(r)
    return None


def start_crawl(mode: str = "discover", only_missing: bool = False,
                ids: list[str] | None = None, force: bool = False,
                dispatch: bool = True) -> dict:
    """Submit crawl jobs to the crawler-platform.

    Refuses if a live platform run already exists unless force=True.
    The `dispatch` parameter is ignored — the platform's own workers handle
    execution without needing GitHub Actions.
    """
    if mode not in ("discover", "monitor"):
        raise ValueError("mode must be 'discover' or 'monitor'")

    existing = active_running_run()
    if existing and not force:
        return {
            "ok": False,
            "reason": "a crawl is already active; pass force=true to start anyway",
            "active_run": existing,
        }

    selected = _select_ids(mode, only_missing, ids)
    if not selected:
        return {"ok": False, "reason": "no municipalities match the selection"}

    reg = _registry_map()
    with CrawlerPlatformClient() as c:
        if not c.ping():
            return {"ok": False, "reason": f"Platform API unreachable at {PLATFORM_API_URL}"}
        # Jobs are named with the muni_id encoded, so the Railway worker's
        # reconcile loop syncs the results and proactively re-runs any that come
        # back empty/failed — the operator does not have to wait or watch.
        job_map = platform_runner.submit_jobs(client=c, muni_ids=selected,
                                              munis_lookup=reg, mode=mode)

    if not job_map:
        return {"ok": False, "reason": "no jobs were submitted to the platform"}

    events.log_event(
        "admin_start_platform", level="info",
        message=f"Operator started platform crawl ({mode}, {len(job_map)} munis)",
        meta={"mode": mode, "job_count": len(job_map)},
    )
    return {"ok": True, "job_map": job_map, "count": len(job_map), "source": "platform"}


def dispatch_github_workflow(mode: str, only_missing: bool) -> dict:
    """Trigger the crawl workflow so real workers spin up without infra access.

    Configure via env: GH_DISPATCH_TOKEN (repo+actions scope), GH_REPO
    ("owner/name"), optional GH_WORKFLOW_FILE (default crawl.yml) and
    GH_WORKFLOW_REF (default main).
    """
    token = os.environ.get("GH_DISPATCH_TOKEN")
    repo = os.environ.get("GH_REPO")
    if not token or not repo:
        return {"dispatched": False, "reason": "GH_DISPATCH_TOKEN/GH_REPO not configured"}

    workflow = os.environ.get("GH_WORKFLOW_FILE", "crawl.yml")
    ref = os.environ.get("GH_WORKFLOW_REF", "main")
    try:
        import requests

        resp = requests.post(
            f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"ref": ref, "inputs": {"mode": mode, "only_missing": bool(only_missing)}},
            timeout=15,
        )
        return {
            "dispatched": resp.status_code == 204,
            "status_code": resp.status_code,
            "detail": None if resp.status_code == 204 else resp.text[:300],
        }
    except Exception as e:  # network / import failure must not break enqueue
        return {"dispatched": False, "reason": str(e)[:200]}


# ── control: run lifecycle ────────────────────────────────────────────────────

def _set_status(run_id: int, status: str, set_finished: bool = False) -> dict:
    now = _now_iso()
    conn = get_connection()
    try:
        if set_finished:
            conn.execute(
                "UPDATE crawl_runs SET status=%s, finished_at=COALESCE(finished_at, %s) WHERE id=%s",
                (status, now, run_id),
            )
        else:
            conn.execute(
                "UPDATE crawl_runs SET status=%s WHERE id=%s", (status, run_id)
            )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "run_id": run_id, "status": status}


def pause_run(run_id: int) -> dict:
    events.log_event("admin_pause", run_id=run_id, message=f"Run {run_id} paused")
    return _set_status(run_id, "paused")


def resume_run(run_id: int) -> dict:
    now = _now_iso()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE crawl_runs SET status='running', finished_at=NULL, last_heartbeat=%s WHERE id=%s",
            (now, run_id),
        )
        conn.commit()
    finally:
        conn.close()
    events.log_event("admin_resume", run_id=run_id, message=f"Run {run_id} resumed")
    return {"ok": True, "run_id": run_id, "status": "running"}


def stop_run(run_id: int) -> dict:
    """Graceful halt: workers stop claiming, task states preserved."""
    events.log_event("admin_stop", run_id=run_id, level="warn", message=f"Run {run_id} stopped")
    return _set_status(run_id, "stopped", set_finished=True)


def cancel_run(run_id: int) -> dict:
    """Hard cancel: abandon all non-terminal tasks, finalize the run."""
    now = _now_iso()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE crawl_tasks SET status='dead', error=COALESCE(error,'cancelled by operator'), "
            "lease_expires_at=NULL, updated_at=%s "
            "WHERE run_id=%s AND status IN ('pending','running','failed')",
            (now, run_id),
        )
        conn.execute(
            "UPDATE crawl_runs SET status='cancelled', finished_at=COALESCE(finished_at, %s) WHERE id=%s",
            (now, run_id),
        )
        conn.commit()
    finally:
        conn.close()
    events.log_event("admin_cancel", run_id=run_id, level="warn", message=f"Run {run_id} cancelled")
    return {"ok": True, "run_id": run_id, "status": "cancelled"}


# ── control: recovery ─────────────────────────────────────────────────────────

def reap(run_id: int | None = None, all_runs: bool = False) -> dict:
    """Requeue expired-lease tasks, mark exhausted ones dead, finalize."""
    if all_runs:
        return {"ok": True, "reaped": task_queue.reap_all_active()}
    if run_id is None:
        return {"ok": False, "reason": "run_id required (or all_runs=true)"}
    events.log_event("admin_reap", run_id=run_id, message=f"Run {run_id} reaped")
    return {"ok": True, "progress": task_queue.reap_run(run_id)}


def clear_stale_locks(run_id: int | None = None) -> dict:
    """Release expired leases without killing the run: stuck 'running' tasks
    whose lease has expired return to 'pending' so a healthy worker reclaims
    them. Does not finalize."""
    now = _now_iso()
    conn = get_connection()
    try:
        where = "status='running' AND lease_expires_at IS NOT NULL AND lease_expires_at < %s"
        params: list = [now]
        if run_id is not None:
            where += " AND run_id=%s"
            params.append(run_id)
        before = conn.execute(
            f"SELECT COUNT(*) AS n FROM crawl_tasks WHERE {where}", params
        ).fetchone()["n"]
        conn.execute(
            f"UPDATE crawl_tasks SET status='pending', leased_by=NULL, lease_expires_at=NULL, "
            f"updated_at=%s WHERE {where}",
            [now] + params,
        )
        conn.commit()
    finally:
        conn.close()
    events.log_event("admin_clear_locks", run_id=run_id, message=f"Cleared {before} stale locks")
    return {"ok": True, "cleared": before}


def reset_stuck_run(run_id: int) -> dict:
    """Force-reset a stuck run: every non-terminal task → pending with a clean
    lease and attempts reset, run reopened as running. Use when a run is wedged
    and you want it to start over rather than recover incrementally."""
    now = _now_iso()
    conn = get_connection()
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM crawl_tasks WHERE run_id=%s "
            "AND status IN ('running','failed')", (run_id,)
        ).fetchone()["n"]
        conn.execute(
            "UPDATE crawl_tasks SET status='pending', leased_by=NULL, lease_expires_at=NULL, "
            "attempts=0, error=NULL, updated_at=%s "
            "WHERE run_id=%s AND status IN ('running','failed','dead')",
            (now, run_id),
        )
        conn.execute(
            "UPDATE crawl_runs SET status='running', finished_at=NULL, last_heartbeat=%s WHERE id=%s",
            (now, run_id),
        )
        conn.commit()
    finally:
        conn.close()
    events.log_event("admin_reset_run", run_id=run_id, level="warn",
                     message=f"Run {run_id} force-reset ({n} tasks requeued)")
    return {"ok": True, "run_id": run_id, "requeued": n}


def kill_orphans() -> dict:
    """Close zombie runs: legacy task-less runs left unfinalized by a killed
    process, plus task-based running runs whose workers are all dead get a
    reap pass (recoverable tasks requeued, exhausted ones marked dead)."""
    now = _now_iso()
    closed_legacy = 0
    conn = get_connection()
    try:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM crawl_runs WHERE finished_at IS NULL "
            "AND status='running' AND id NOT IN (SELECT DISTINCT run_id FROM crawl_tasks)"
        ).fetchone()["n"]
        conn.execute(
            "UPDATE crawl_runs SET finished_at=%s, status='done' "
            "WHERE finished_at IS NULL AND status='running' "
            "AND id NOT IN (SELECT DISTINCT run_id FROM crawl_tasks)",
            (now,),
        )
        conn.commit()
        closed_legacy = before
    finally:
        conn.close()
    reaped = task_queue.reap_all_active()
    events.log_event("admin_kill_orphans", level="warn",
                     message=f"Closed {closed_legacy} zombie runs; reaped {len(reaped)} active runs")
    return {"ok": True, "closed_legacy_runs": closed_legacy, "reaped_runs": len(reaped)}


# ── control: task / municipality level ────────────────────────────────────────

def _reopen_run_if_finished(conn, run_id: int) -> None:
    conn.execute(
        "UPDATE crawl_runs SET status='running', finished_at=NULL WHERE id=%s "
        "AND (finished_at IS NOT NULL OR status IN ('done','stopped','cancelled'))",
        (run_id,),
    )


def retry_task(task_id: int) -> dict:
    """Requeue a single failed/dead/skipped task and reopen its run."""
    now = _now_iso()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT run_id, municipality_id FROM crawl_tasks WHERE id=%s", (task_id,)
        ).fetchone()
        if not row:
            return {"ok": False, "reason": f"task {task_id} not found"}
        conn.execute(
            "UPDATE crawl_tasks SET status='pending', leased_by=NULL, lease_expires_at=NULL, "
            "attempts=0, error=NULL, updated_at=%s WHERE id=%s",
            (now, task_id),
        )
        _reopen_run_if_finished(conn, row["run_id"])
        conn.commit()
    finally:
        conn.close()
    events.log_event("admin_retry_task", run_id=row["run_id"], task_id=task_id,
                     municipality_id=row["municipality_id"],
                     message=f"Retry {row['municipality_id']}")
    return {"ok": True, "task_id": task_id, "run_id": row["run_id"]}


def retry_all_failed(run_id: int) -> dict:
    now = _now_iso()
    conn = get_connection()
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM crawl_tasks WHERE run_id=%s "
            "AND status IN ('failed','dead','skipped')", (run_id,)
        ).fetchone()["n"]
        conn.execute(
            "UPDATE crawl_tasks SET status='pending', leased_by=NULL, lease_expires_at=NULL, "
            "attempts=0, error=NULL, updated_at=%s "
            "WHERE run_id=%s AND status IN ('failed','dead','skipped')",
            (now, run_id),
        )
        _reopen_run_if_finished(conn, run_id)
        conn.commit()
    finally:
        conn.close()
    events.log_event("admin_retry_all", run_id=run_id,
                     message=f"Retry all failed in run {run_id} ({n} tasks)")
    return {"ok": True, "run_id": run_id, "requeued": n}


def reset_task(task_id: int) -> dict:
    """Alias of retry_task — clears state back to pending."""
    return retry_task(task_id)


def skip_municipality(run_id: int, municipality_id: str) -> dict:
    """Mark a municipality's task as skipped (terminal, never retried)."""
    now = _now_iso()
    conn = get_connection()
    try:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM crawl_tasks WHERE run_id=%s AND municipality_id=%s",
            (run_id, municipality_id),
        ).fetchone()["n"]
        if not n:
            return {"ok": False, "reason": "no matching task"}
        conn.execute(
            "UPDATE crawl_tasks SET status='skipped', leased_by=NULL, lease_expires_at=NULL, "
            "error='skipped by operator', updated_at=%s WHERE run_id=%s AND municipality_id=%s",
            (now, run_id, municipality_id),
        )
        conn.commit()
    finally:
        conn.close()
    events.log_event("admin_skip", run_id=run_id, municipality_id=municipality_id,
                     message=f"Skipped {municipality_id}")
    return {"ok": True, "run_id": run_id, "municipality_id": municipality_id}


def recrawl_municipality(municipality_id: str, mode: str = "discover",
                         dispatch: bool = True) -> dict:
    """Submit a single-municipality crawl job to the platform."""
    reg = _registry_map()
    if municipality_id not in reg:
        return {"ok": False, "reason": f"unknown municipality '{municipality_id}'"}

    with CrawlerPlatformClient() as c:
        if not c.ping():
            return {"ok": False, "reason": f"Platform API unreachable at {PLATFORM_API_URL}"}
        job_map = platform_runner.submit_jobs(client=c, muni_ids=[municipality_id],
                                              munis_lookup=reg, mode=mode)

    job_id = job_map.get(municipality_id)
    if not job_id:
        return {"ok": False, "reason": "nothing to crawl (no seeds for monitor mode?)"}

    events.log_event(
        "admin_recrawl", municipality_id=municipality_id,
        message=f"Re-crawl {municipality_id} via platform (job {job_id})",
        meta={"job_id": job_id, "mode": mode},
    )
    return {"ok": True, "job_id": job_id, "municipality_id": municipality_id}
