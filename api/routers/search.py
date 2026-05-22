import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_db
from api.schemas import SearchResult, PaginatedResponse

router = APIRouter(prefix="/search", tags=["search"])

_MUNI_FILE = Path("municipalities.json")


def _muni_name_map() -> dict[str, str]:
    try:
        data = json.loads(_MUNI_FILE.read_text(encoding="utf-8"))
        return {m["id"]: m["name"] for m in data}
    except Exception:
        return {}


def _doc_title(url: str) -> str:
    path = url.rstrip("/").split("/")[-1]
    name = path.split("?")[0]
    return name if name else url


@router.get("", response_model=PaginatedResponse)
def search(
    q: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by type: page | document"),
    municipality_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db=Depends(get_db),
):
    pattern = f"%{q}%"
    names = _muni_name_map()
    results: list[SearchResult] = []

    if type in (None, "page"):
        muni_filter = "AND municipality_id = %s" if municipality_id else ""
        page_rows = db.execute(
            f"""
            SELECT 'page' AS type, municipality_id, url, NULL AS file_type,
                   title, snippet, NULL AS last_seen, last_crawled
            FROM pages
            WHERE (url ILIKE %s OR title ILIKE %s OR snippet ILIKE %s)
            {muni_filter}
            ORDER BY
                CASE WHEN title ILIKE %s THEN 0 ELSE 1 END,
                last_crawled DESC
            LIMIT %s OFFSET %s
            """,
            (
                (pattern, pattern, pattern, municipality_id, pattern, limit, offset)
                if municipality_id
                else (pattern, pattern, pattern, pattern, limit, offset)
            ),
        ).fetchall()

        for r in page_rows:
            results.append(SearchResult(
                type=r["type"],
                municipality_id=r["municipality_id"],
                municipality_name=names.get(r["municipality_id"], r["municipality_id"]),
                url=r["url"],
                file_type=r["file_type"],
                title=r["title"],
                snippet=r["snippet"],
                last_seen=r["last_seen"],
                last_crawled=r["last_crawled"],
            ))

    if type in (None, "document"):
        muni_filter = "AND municipality_id = %s" if municipality_id else ""
        doc_rows = db.execute(
            f"""
            SELECT 'document' AS type, municipality_id, url, file_type,
                   NULL AS last_crawled, last_seen
            FROM documents
            WHERE url ILIKE %s
            {muni_filter}
            ORDER BY last_seen DESC
            LIMIT %s OFFSET %s
            """,
            (
                (pattern, municipality_id, limit, offset)
                if municipality_id
                else (pattern, limit, offset)
            ),
        ).fetchall()

        for r in doc_rows:
            results.append(SearchResult(
                type=r["type"],
                municipality_id=r["municipality_id"],
                municipality_name=names.get(r["municipality_id"], r["municipality_id"]),
                url=r["url"],
                file_type=r["file_type"],
                title=_doc_title(r["url"]),
                snippet=None,
                last_seen=r["last_seen"],
                last_crawled=r["last_crawled"],
            ))

    return PaginatedResponse(
        total=len(results),
        page=offset // limit + 1,
        page_size=limit,
        results=results,
    )
