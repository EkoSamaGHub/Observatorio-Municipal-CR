import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db
from api.schemas import CrawlRun

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=list[CrawlRun])
def list_runs(
    limit: int = 20,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    rows = db.execute(
        "SELECT * FROM crawl_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [CrawlRun(**dict(r)) for r in rows]


@router.get("/{run_id}", response_model=CrawlRun)
def get_run(run_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return CrawlRun(**dict(row))
