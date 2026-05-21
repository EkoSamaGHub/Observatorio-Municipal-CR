import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from api.deps import get_db
from api.schemas import Municipality, MunicipalityStats, Page, Document, Diff

router = APIRouter(prefix="/municipalities", tags=["municipalities"])

MUNICIPALITIES_FILE = Path("municipalities.json")


def _load_registry() -> list[dict]:
    with open(MUNICIPALITIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_muni_or_404(muni_id: str) -> dict:
    registry = _load_registry()
    match = next((m for m in registry if m["id"] == muni_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Municipality '{muni_id}' not found")
    return match


@router.get("", response_model=list[MunicipalityStats])
def list_municipalities(
    province: Optional[str] = None,
    active: bool = True,
    db: sqlite3.Connection = Depends(get_db),
):
    registry = _load_registry()

    if active:
        registry = [m for m in registry if m["active"]]
    if province:
        registry = [m for m in registry if m["province"].lower() == province.lower()]

    results = []
    for m in registry:
        row = db.execute("""
            SELECT COUNT(*) as pages, MAX(last_crawled) as last_crawled
            FROM pages WHERE municipality_id = ?
        """, (m["id"],)).fetchone()

        docs = db.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE municipality_id = ?",
            (m["id"],)
        ).fetchone()

        changes = db.execute(
            "SELECT COUNT(*) as cnt FROM page_diffs WHERE municipality_id = ?",
            (m["id"],)
        ).fetchone()

        results.append(MunicipalityStats(
            **m,
            pages_crawled=row["pages"] or 0,
            documents_found=docs["cnt"] or 0,
            last_crawled=row["last_crawled"],
            changes_detected=changes["cnt"] or 0,
        ))

    return results


@router.get("/{muni_id}", response_model=MunicipalityStats)
def get_municipality(muni_id: str, db: sqlite3.Connection = Depends(get_db)):
    m = _get_muni_or_404(muni_id)

    row = db.execute("""
        SELECT COUNT(*) as pages, MAX(last_crawled) as last_crawled
        FROM pages WHERE municipality_id = ?
    """, (muni_id,)).fetchone()

    docs = db.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE municipality_id = ?",
        (muni_id,)
    ).fetchone()

    changes = db.execute(
        "SELECT COUNT(*) as cnt FROM page_diffs WHERE municipality_id = ?",
        (muni_id,)
    ).fetchone()

    return MunicipalityStats(
        **m,
        pages_crawled=row["pages"] or 0,
        documents_found=docs["cnt"] or 0,
        last_crawled=row["last_crawled"],
        changes_detected=changes["cnt"] or 0,
    )


@router.get("/{muni_id}/pages", response_model=list[Page])
def get_municipality_pages(
    muni_id: str,
    depth: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    _get_muni_or_404(muni_id)

    query = "SELECT * FROM pages WHERE municipality_id = ?"
    params: list = [muni_id]

    if depth is not None:
        query += " AND depth = ?"
        params.append(depth)

    query += " ORDER BY depth, last_crawled DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = db.execute(query, params).fetchall()
    return [Page(**dict(r)) for r in rows]


@router.get("/{muni_id}/documents", response_model=list[Document])
def get_municipality_documents(
    muni_id: str,
    file_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    _get_muni_or_404(muni_id)

    query = "SELECT * FROM documents WHERE municipality_id = ?"
    params: list = [muni_id]

    if file_type:
        query += " AND file_type = ?"
        params.append(file_type)

    query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = db.execute(query, params).fetchall()
    return [Document(downloaded=bool(r["downloaded"]), **{k: v for k, v in dict(r).items() if k != "downloaded"}) for r in rows]


@router.get("/{muni_id}/diffs", response_model=list[Diff])
def get_municipality_diffs(
    muni_id: str,
    limit: int = 50,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    _get_muni_or_404(muni_id)

    rows = db.execute("""
        SELECT * FROM page_diffs WHERE municipality_id = ?
        ORDER BY detected_at DESC LIMIT ? OFFSET ?
    """, (muni_id, limit, offset)).fetchall()

    return [Diff(**dict(r)) for r in rows]
