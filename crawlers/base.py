from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CrawlResult:
    url: str
    municipality_id: str
    status_code: Optional[int]
    content_type: str
    content_hash: str
    html: str
    links: list[str] = field(default_factory=list)
    pdfs: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    depth: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and self.status_code == 200


@dataclass
class CrawlSummary:
    results: list[CrawlResult]
    terminated_by: str          # "complete" | "max_pages"
    sitemap_total: int = 0      # URLs found in sitemap (0 = no sitemap)
    pages_fetched: int = 0
    completeness_pct: float = 0.0  # pages_fetched / sitemap_total * 100


class BaseCrawler(ABC):

    @abstractmethod
    def fetch(self, url: str) -> CrawlResult:
        """Fetch a single URL and return a CrawlResult."""

    @abstractmethod
    def crawl(
        self,
        municipality_id: str,
        root_url: str,
        max_depth: int = 2,
        mode: str = "discover",
        known_urls: set[str] | None = None,
        seed_links: set[str] | None = None,
        sitemap_urls: list[str] | None = None,
    ) -> CrawlSummary:
        """Crawl a municipality site and return a CrawlSummary."""
