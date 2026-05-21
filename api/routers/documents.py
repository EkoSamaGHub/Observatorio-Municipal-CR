import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas import Document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[Document])
def list_documents(
    file_type: Optional[str] = None,
    municipality_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    query = "SELECT * FROM documents WHERE 1=1"
    params: list = []

    if file_type:
        query += " AND file_type = ?"
        params.append(file_type)

    if municipality_id:
        query += " AND municipality_id = ?"
        params.append(municipality_id)

    query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = db.execute(query, params).fetchall()
    return [Document(downloaded=bool(r["downloaded"]), **{k: v for k, v in dict(r).items() if k != "downloaded"}) for r in rows]
