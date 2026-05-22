import json
import pathlib
from typing import Optional

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas import DomainExpiry, SSLReport

router = APIRouter(prefix="/reports", tags=["reports"])

_REGISTRY_CACHE: dict[str, dict] = {}


def _registry() -> dict[str, dict]:
    global _REGISTRY_CACHE
    if not _REGISTRY_CACHE:
        path = pathlib.Path(__file__).parent.parent.parent / "municipalities.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _REGISTRY_CACHE = {m["id"]: m for m in data}
    return _REGISTRY_CACHE


def _enrich(row: dict) -> dict:
    muni = _registry().get(row["municipality_id"], {})
    row["municipality_name"] = muni.get("name", row["municipality_id"])
    row["province"] = muni.get("province", "")
    return row


@router.get("/ssl", response_model=list[SSLReport])
def get_ssl_reports(limit: int = 200, offset: int = 0, db=Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM ssl_reports ORDER BY checked_at DESC LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()
    return [SSLReport(**_enrich(dict(r))) for r in rows]


@router.get("/domains", response_model=list[DomainExpiry])
def get_domain_expiry(limit: int = 200, offset: int = 0, db=Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM domain_expiry ORDER BY expiry_date ASC LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()
    return [DomainExpiry(**_enrich(dict(r))) for r in rows]
