from typing import Optional
from pydantic import BaseModel


class Municipality(BaseModel):
    id: str
    province: str
    name: str
    root_url: str
    active: bool


class MunicipalityStats(Municipality):
    pages_crawled: int = 0
    documents_found: int = 0
    last_crawled: Optional[str] = None
    changes_detected: int = 0


class Page(BaseModel):
    id: int
    municipality_id: str
    url: str
    content_type: Optional[str]
    content_hash: Optional[str]
    status_code: Optional[int]
    depth: int
    last_crawled: str


class Document(BaseModel):
    id: int
    municipality_id: str
    url: str
    file_type: Optional[str]
    content_hash: Optional[str]
    downloaded: bool
    first_seen: str
    last_seen: str


class Diff(BaseModel):
    id: int
    municipality_id: str
    url: str
    old_hash: Optional[str]
    new_hash: Optional[str]
    detected_at: str


class CrawlRun(BaseModel):
    id: int
    started_at: str
    finished_at: Optional[str]
    municipalities: int
    pages_crawled: int
    pages_changed: int
    pages_new: int
    errors: int


class SearchResult(BaseModel):
    type: str
    municipality_id: str
    url: str
    file_type: Optional[str] = None
    last_seen: Optional[str] = None
    last_crawled: Optional[str] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list


class SSLReport(BaseModel):
    id: int
    municipality_id: str
    municipality_name: str
    province: str
    domain: str
    grade: Optional[str] = None
    cert_expiry: Optional[str] = None
    ip_address: Optional[str] = None
    has_warnings: bool = False
    checked_at: str


class DomainExpiry(BaseModel):
    id: int
    municipality_id: str
    municipality_name: str
    province: str
    domain: str
    registrar: Optional[str] = None
    expiry_date: Optional[str] = None
    creation_date: Optional[str] = None
    checked_at: str
