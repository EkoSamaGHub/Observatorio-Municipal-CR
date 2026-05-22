from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db
from api.schemas import CrawlRun
from configs.db import BACKEND

router = APIRouter(prefix="/runs", tags=["runs"])

# Duration expression varies by backend since timestamps are stored as TEXT
if BACKEND == "postgres":
    _DURATION_EXPR = (
        "EXTRACT(EPOCH FROM (finished_at::timestamptz - started_at::timestamptz)) / 3600.0"
    )
else:
    _DURATION_EXPR = "(julianday(finished_at) - julianday(started_at)) * 24"


@router.get("", response_model=list[CrawlRun])
def list_runs(
    limit: int = 20,
    offset: int = 0,
    db=Depends(get_db),
):
    rows = db.execute(
        "SELECT * FROM crawl_runs ORDER BY started_at DESC LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()
    return [CrawlRun(**r) for r in rows]


@router.get("/active")
def get_active_run(db=Depends(get_db)):
    run = db.execute(
        "SELECT * FROM crawl_runs WHERE finished_at IS NULL ORDER BY started_at DESC LIMIT 1"
    ).fetchone()

    if not run:
        return {"active": False}

    started_at = run["started_at"]

    munis_done = db.execute(
        "SELECT COUNT(DISTINCT municipality_id) AS n FROM pages WHERE last_crawled >= %s",
        (started_at,),
    ).fetchone()["n"]

    munis_with_data = db.execute(
        "SELECT COUNT(DISTINCT municipality_id) AS n FROM pages"
    ).fetchone()["n"]

    pages_crawled = db.execute(
        "SELECT COUNT(*) AS n FROM pages WHERE last_crawled >= %s",
        (started_at,),
    ).fetchone()["n"]

    latest = db.execute(
        "SELECT municipality_id, url FROM pages WHERE last_crawled >= %s ORDER BY last_crawled DESC LIMIT 1",
        (started_at,),
    ).fetchone()

    return {
        "active": True,
        "run_id": run["id"],
        "started_at": started_at,
        "municipalities_done": munis_done,
        "municipalities_with_data": munis_with_data,
        "municipalities_total": 84,
        "pages_crawled": pages_crawled,
        "current_municipality": latest["municipality_id"] if latest else None,
        "current_url": latest["url"] if latest else None,
    }


@router.get("/stats")
def get_run_stats(db=Depends(get_db)):
    """Real investment metrics: actual crawl hours from the database."""
    runs_row = db.execute(f"""
        SELECT
            COUNT(*)   AS total_runs,
            COALESCE(SUM(
                CASE WHEN finished_at IS NOT NULL
                THEN {_DURATION_EXPR}
                ELSE 0 END
            ), 0)      AS completed_hours,
            MIN(started_at) AS first_run_at
        FROM crawl_runs
    """).fetchone()

    pages_row = db.execute("SELECT COUNT(*) AS n FROM pages").fetchone()
    docs_row  = db.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
    dev_row   = db.execute(
        "SELECT COALESCE(SUM(hours), 0) AS total, COUNT(*) AS sessions FROM dev_sessions"
    ).fetchone()

    active = db.execute(
        "SELECT started_at FROM crawl_runs WHERE finished_at IS NULL ORDER BY started_at DESC LIMIT 1"
    ).fetchone()

    return {
        "total_runs":        runs_row["total_runs"],
        "completed_hours":   round(runs_row["completed_hours"], 2),
        "first_run_at":      runs_row["first_run_at"],
        "total_pages":       pages_row["n"],
        "total_docs":        docs_row["n"],
        "active_started_at": active["started_at"] if active else None,
        "dev_hours":         round(dev_row["total"], 2),
        "dev_sessions":      dev_row["sessions"],
    }


@router.get("/{run_id}", response_model=CrawlRun)
def get_run(run_id: int, db=Depends(get_db)):
    row = db.execute(
        "SELECT * FROM crawl_runs WHERE id = %s", (run_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return CrawlRun(**row)
