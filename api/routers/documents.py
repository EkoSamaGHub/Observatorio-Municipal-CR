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
    db=Depends(get_db),
):
    query = "SELECT * FROM documents WHERE 1=1"
    params: list = []

    if file_type:
        query += " AND file_type = %s"
        params.append(file_type)

    if municipality_id:
        query += " AND municipality_id = %s"
        params.append(municipality_id)

    query += " ORDER BY last_seen DESC LIMIT %s OFFSET %s"
    params += [limit, offset]

    rows = db.execute(query, params).fetchall()
    return [Document(downloaded=bool(r["downloaded"]), **{k: v for k, v in r.items() if k != "downloaded"}) for r in rows]
