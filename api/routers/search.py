import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_db
from api.schemas import SearchResult, PaginatedResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=PaginatedResponse)
def search(
    q: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by type: page | document"),
    municipality_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    pattern = f"%{q}%"
    results: list[SearchResult] = []

    if type in (None, "page"):
        page_rows = db.execute("""
            SELECT 'page' as type, municipality_id, url, NULL as file_type,
                   NULL as last_seen, last_crawled
            FROM pages
            WHERE url LIKE ?
            """ + ("AND municipality_id = ?" if municipality_id else "") + """
            ORDER BY last_crawled DESC
            LIMIT ? OFFSET ?
        """, (
            (pattern, municipality_id, limit, offset)
            if municipality_id
            else (pattern, limit, offset)
        )).fetchall()

        results += [SearchResult(**dict(r)) for r in page_rows]

    if type in (None, "document"):
        doc_rows = db.execute("""
            SELECT 'document' as type, municipality_id, url, file_type,
                   last_seen, NULL as last_crawled
            FROM documents
            WHERE url LIKE ?
            """ + ("AND municipality_id = ?" if municipality_id else "") + """
            ORDER BY last_seen DESC
            LIMIT ? OFFSET ?
        """, (
            (pattern, municipality_id, limit, offset)
            if municipality_id
            else (pattern, limit, offset)
        )).fetchall()

        results += [SearchResult(**dict(r)) for r in doc_rows]

    return PaginatedResponse(
        total=len(results),
        page=offset // limit + 1,
        page_size=limit,
        results=results,
    )
