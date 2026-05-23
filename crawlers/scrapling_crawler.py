import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse

from scrapling.fetchers import Fetcher

from configs.constants import IGNORED_EXTENSIONS, USER_AGENT
from crawlers.base import BaseCrawler, CrawlResult, CrawlSummary
from modules.classifiers import classify_url
from modules.hashing import sha256_hash
from modules.logger import logger
from modules.retry_manager import retry
from modules.robots import is_allowed
from modules.url_manager import normalize_url, should_ignore


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

CRAWL_MODES = ("discover", "monitor")


class ScraplingCrawler(BaseCrawler):

    def __init__(self, request_delay: float = 2.0, max_pages: int = 1000, respect_robots: bool = True, verify_ssl: bool = False):
        self.request_delay = request_delay
        self.max_pages = max_pages
        self.respect_robots = respect_robots
        self.verify_ssl = verify_ssl
        self._fetcher = Fetcher()

    def fetch(self, url: str, municipality_id: str = "", depth: int = 0) -> CrawlResult:
        try:
            verify = self.verify_ssl
            response = retry(
                lambda: self._fetcher.get(url, verify=verify),
                retries=3,
                delay=2,
            )

            html = response.html_content or ""
            links, pdfs, emails = self._extract(response, url)

            return CrawlResult(
                url=url,
                municipality_id=municipality_id,
                status_code=response.status,
                content_type=response.headers.get("content-type", "text/html"),
                content_hash=sha256_hash(html),
                html=html,
                links=links,
                pdfs=pdfs,
                emails=emails,
                depth=depth,
            )

        except Exception as e:
            logger.error(f"Fetch failed [{municipality_id}] {url}: {e}")
            return CrawlResult(
                url=url,
                municipality_id=municipality_id,
                status_code=None,
                content_type="",
                content_hash="",
                html="",
                depth=depth,
                error=str(e),
            )

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
        if mode not in CRAWL_MODES:
            raise ValueError(f"mode must be one of {CRAWL_MODES}")

        if mode == "monitor":
            return self._crawl_monitor(municipality_id, known_urls or set())

        return self._crawl_discover(
            municipality_id, root_url, max_depth,
            known_urls=known_urls or set(),
            seed_links=seed_links or set(),
            sitemap_urls=sitemap_urls or [],
        )

    def _crawl_discover(
        self,
        municipality_id: str,
        root_url: str,
        max_depth: int,
        known_urls: set[str],
        seed_links: set[str],
        sitemap_urls: list[str],
    ) -> CrawlSummary:
        root_domain = urlparse(root_url).netloc
        visited: set[str] = set(known_urls)
        results: list[CrawlResult] = []

        norm_root = normalize_url(root_url)

        # Build queue: root → sitemap URLs → stored link graph edges
        queue: deque[tuple[str, int]] = deque()
        queue.append((root_url, 0))

        for url in sitemap_urls:
            norm = normalize_url(url)
            if norm not in visited:
                queue.append((norm, 1))

        for link in seed_links:
            norm = normalize_url(link)
            if norm not in visited:
                queue.append((norm, 1))

        # Always re-fetch root on return visits to get fresh outgoing links.
        # Without this, a fully-indexed site would never discover new pages:
        # seed_links are stale (all in known_urls), so nothing new enters the queue.
        if norm_root in visited:
            visited.discard(norm_root)

        sitemap_total = len(sitemap_urls)
        fetched = 0
        skipped = 0
        terminated_by = "complete"

        while queue:
            if fetched >= self.max_pages:
                terminated_by = "max_pages"
                break

            url, depth = queue.popleft()
            normalized = normalize_url(url)

            if normalized in visited:
                skipped += 1
                continue
            if should_ignore(normalized):
                continue
            if self._has_ignored_extension(normalized):
                continue
            if urlparse(normalized).netloc != root_domain:
                continue
            if self.respect_robots and not is_allowed(normalized):
                logger.debug(f"[{municipality_id}] robots.txt disallows {normalized}")
                continue

            visited.add(normalized)
            logger.info(f"[{municipality_id}][discover] depth={depth} {normalized}")

            result = self.fetch(normalized, municipality_id=municipality_id, depth=depth)
            results.append(result)
            fetched += 1

            if result.success and depth < max_depth:
                for link in result.links:
                    if normalize_url(link) not in visited:
                        queue.append((link, depth + 1))

            if self.request_delay:
                time.sleep(self.request_delay)

        completeness = (fetched / sitemap_total * 100) if sitemap_total > 0 else 0.0

        logger.info(
            f"[{municipality_id}] discover complete — fetched={fetched} "
            f"skipped_known={skipped} terminated_by={terminated_by} "
            f"sitemap_total={sitemap_total} completeness={completeness:.1f}%"
        )

        return CrawlSummary(
            results=results,
            terminated_by=terminated_by,
            sitemap_total=sitemap_total,
            pages_fetched=fetched,
            completeness_pct=round(completeness, 1),
        )

    def _crawl_monitor(self, municipality_id: str, known_urls: set[str]) -> CrawlSummary:
        results: list[CrawlResult] = []

        if not known_urls:
            logger.info(f"[{municipality_id}] monitor: no known pages, nothing to check")
            return CrawlSummary(results=[], terminated_by="complete", pages_fetched=0)

        logger.info(f"[{municipality_id}] monitor: re-checking {len(known_urls)} known pages")

        for url in known_urls:
            if self.respect_robots and not is_allowed(url):
                continue
            logger.info(f"[{municipality_id}][monitor] {url}")
            result = self.fetch(url, municipality_id=municipality_id, depth=0)
            results.append(result)
            if self.request_delay:
                time.sleep(self.request_delay)

        return CrawlSummary(
            results=results,
            terminated_by="complete",
            pages_fetched=len(results),
        )

    def _extract(self, response, base_url: str) -> tuple[list[str], list[str], list[str]]:
        links: list[str] = []
        pdfs: list[str] = []
        emails: list[str] = []

        for href in response.css("a::attr(href)").getall():
            href = href.strip()
            if href.startswith("mailto:"):
                emails.append(href[7:])
                continue
            absolute = urljoin(base_url, href)
            normalized = normalize_url(absolute)
            if should_ignore(normalized):
                continue
            links.append(normalized)
            if classify_url(normalized) == "pdf":
                pdfs.append(normalized)

        text = response.get_all_text() or ""
        emails += EMAIL_RE.findall(text)
        emails = list(set(emails))

        return links, pdfs, emails

    def _has_ignored_extension(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in IGNORED_EXTENSIONS)
