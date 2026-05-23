"""
Persistent crawl event log.

Lifecycle functions (task_queue) and admin operations emit structured events
here so the admin dashboard has a searchable, filterable audit trail that
survives worker crashes and redeploys — unlike stdout logs, which are gone the
moment Railway/GitHub Actions recycles the container.

Logging must never break a crawl: every write is wrapped so a logging failure
degrades to a no-op instead of aborting the caller.
"""

import json
from datetime import datetime, timezone

from configs.db import get_connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    event: str,
    *,
    level: str = "info",
    run_id: int | None = None,
    task_id: int | None = None,
    municipality_id: str | None = None,
    message: str | None = None,
    meta: dict | None = None,
    conn=None,
) -> None:
    """Append one structured event. Best-effort: swallows its own errors."""
    own_conn = conn is None
    try:
        if own_conn:
            conn = get_connection()
        conn.execute(
            "INSERT INTO crawl_events "
            "(run_id, task_id, municipality_id, level, event, message, meta, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                run_id,
                task_id,
                municipality_id,
                level,
                event,
                (message or "")[:1000] or None,
                json.dumps(meta) if meta else None,
                _now_iso(),
            ),
        )
        conn.commit()
    except Exception:
        # Never let observability take down the pipeline.
        pass
    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def query_events(
    *,
    run_id: int | None = None,
    municipality_id: str | None = None,
    level: str | None = None,
    event: str | None = None,
    search: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Filterable event query, newest first."""
    clauses: list[str] = []
    params: list = []
    if run_id is not None:
        clauses.append("run_id = %s")
        params.append(run_id)
    if municipality_id:
        clauses.append("municipality_id = %s")
        params.append(municipality_id)
    if level:
        clauses.append("level = %s")
        params.append(level)
    if event:
        clauses.append("event = %s")
        params.append(event)
    if search:
        clauses.append("(message LIKE %s OR event LIKE %s OR municipality_id LIKE %s)")
        like = f"%{search}%"
        params += [like, like, like]
    if since:
        clauses.append("created_at >= %s")
        params.append(since)
    if until:
        clauses.append("created_at <= %s")
        params.append(until)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT id, run_id, task_id, municipality_id, level, event, message, meta, created_at "
        f"FROM crawl_events{where} ORDER BY id DESC LIMIT %s OFFSET %s"
    )
    params += [limit, offset]

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    for r in rows:
        if r.get("meta"):
            try:
                r["meta"] = json.loads(r["meta"])
            except (ValueError, TypeError):
                pass
    return rows
