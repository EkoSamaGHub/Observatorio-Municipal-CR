"""
Admin control-plane API.

Security model: every endpoint requires the `ADMIN_TOKEN` env var to be set and
the caller to present it (header `X-Admin-Token: <token>` or
`Authorization: Bearer <token>`). If `ADMIN_TOKEN` is unset the whole router is
disabled (503) — the control plane is never exposed publicly by default.

These endpoints are the control plane only; they mutate durable queue state in
Postgres. The actual crawling is performed by the distributed workers
(GitHub Actions + Railway worker.py) that already obey that state.
"""

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from modules import admin_ops, events

router = APIRouter(prefix="/admin", tags=["admin"])


# ── auth ──────────────────────────────────────────────────────────────────────

def require_admin(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="Admin disabled: ADMIN_TOKEN not set")
    provided = x_admin_token
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1]
    if not provided or not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


_auth = [Depends(require_admin)]


# ── request bodies ──────────────────────────────────────────────────────────

class StartCrawlBody(BaseModel):
    mode: str = "discover"
    only_missing: bool = False
    ids: list[str] | None = None
    force: bool = False
    dispatch: bool = True


class RecrawlBody(BaseModel):
    mode: str = "discover"
    dispatch: bool = True


# ── observability (GET) ─────────────────────────────────────────────────────

@router.get("/overview", dependencies=_auth)
def get_overview():
    return admin_ops.overview()


@router.get("/runs", dependencies=_auth)
def get_runs(limit: int = 25):
    return admin_ops.list_runs(limit=limit)


@router.get("/runs/{run_id}/tasks", dependencies=_auth)
def get_run_tasks(run_id: int):
    return admin_ops.run_tasks(run_id)


@router.get("/workers", dependencies=_auth)
def get_workers():
    return admin_ops.workers()


@router.get("/logs", dependencies=_auth)
def get_logs(
    run_id: int | None = None,
    municipality_id: str | None = None,
    level: str | None = None,
    event: str | None = None,
    search: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    return events.query_events(
        run_id=run_id, municipality_id=municipality_id, level=level, event=event,
        search=search, since=since, until=until, limit=min(limit, 1000), offset=offset,
    )


# ── crawl control (POST) ────────────────────────────────────────────────────

@router.post("/crawl/start", dependencies=_auth)
def start_crawl(body: StartCrawlBody):
    try:
        return admin_ops.start_crawl(
            mode=body.mode, only_missing=body.only_missing, ids=body.ids,
            force=body.force, dispatch=body.dispatch,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/crawl/{run_id}/pause", dependencies=_auth)
def pause(run_id: int):
    return admin_ops.pause_run(run_id)


@router.post("/crawl/{run_id}/resume", dependencies=_auth)
def resume(run_id: int):
    return admin_ops.resume_run(run_id)


@router.post("/crawl/{run_id}/stop", dependencies=_auth)
def stop(run_id: int):
    return admin_ops.stop_run(run_id)


@router.post("/crawl/{run_id}/cancel", dependencies=_auth)
def cancel(run_id: int):
    return admin_ops.cancel_run(run_id)


@router.post("/crawl/{run_id}/reset", dependencies=_auth)
def reset_stuck(run_id: int):
    return admin_ops.reset_stuck_run(run_id)


@router.post("/crawl/{run_id}/reap", dependencies=_auth)
def reap(run_id: int):
    return admin_ops.reap(run_id=run_id)


@router.post("/crawl/{run_id}/retry-failed", dependencies=_auth)
def retry_failed(run_id: int):
    return admin_ops.retry_all_failed(run_id)


@router.post("/crawl/clear-locks", dependencies=_auth)
def clear_locks(run_id: int | None = None):
    return admin_ops.clear_stale_locks(run_id=run_id)


@router.post("/crawl/kill-orphans", dependencies=_auth)
def kill_orphans():
    return admin_ops.kill_orphans()


# ── task / municipality control (POST) ──────────────────────────────────────

@router.post("/tasks/{task_id}/retry", dependencies=_auth)
def retry_task(task_id: int):
    return admin_ops.retry_task(task_id)


@router.post("/tasks/{task_id}/reset", dependencies=_auth)
def reset_task(task_id: int):
    return admin_ops.reset_task(task_id)


@router.post("/runs/{run_id}/municipalities/{municipality_id}/skip", dependencies=_auth)
def skip_muni(run_id: int, municipality_id: str):
    return admin_ops.skip_municipality(run_id, municipality_id)


@router.post("/municipalities/{municipality_id}/recrawl", dependencies=_auth)
def recrawl_muni(municipality_id: str, body: RecrawlBody):
    return admin_ops.recrawl_municipality(
        municipality_id, mode=body.mode, dispatch=body.dispatch
    )
