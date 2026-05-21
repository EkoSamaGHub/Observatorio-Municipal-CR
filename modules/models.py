from dataclasses import dataclass
from datetime import datetime


@dataclass
class Municipality:
    id: str
    name: str
    province: str
    root_url: str


@dataclass
class Page:
    url: str
    municipality_id: str
    depth: int
    status_code: int
    content_type: str
    content_hash: str
    last_crawled: datetime


@dataclass
class Document:
    url: str
    municipality_id: str
    file_type: str
    content_hash: str
