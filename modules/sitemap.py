import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from modules.logger import logger

_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
}

_COMMON_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemaps/sitemap.xml",
    "/wp-sitemap.xml",
]

_TIMEOUT = 10


def _get(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=_TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logger.debug(f"Sitemap fetch failed {url}: {e}")
    return None


def _parse_sitemap(xml_text: str, root_domain: str, depth: int = 0) -> list[str]:
    """Parse a sitemap or sitemap index, returning all <loc> URLs."""
    if depth > 3:
        return []

    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
        tag = root.tag.lower()

        # Sitemap index — recurse into each referenced sitemap
        if "sitemapindex" in tag:
            for sitemap in root.findall(".//sm:sitemap/sm:loc", _NS) or root.findall(".//sitemap/loc"):
                loc = sitemap.text.strip() if sitemap.text else ""
                if loc:
                    sub = _get(loc)
                    if sub:
                        urls.extend(_parse_sitemap(sub, root_domain, depth + 1))

        # Regular urlset
        else:
            for loc in root.findall(".//sm:url/sm:loc", _NS) or root.findall(".//url/loc"):
                if loc.text:
                    url = loc.text.strip()
                    if urlparse(url).netloc == root_domain:
                        urls.append(url)

    except ET.ParseError as e:
        logger.debug(f"Sitemap XML parse error: {e}")

    return urls


def _sitemap_urls_from_robots(root_url: str) -> list[str]:
    """Extract Sitemap: directives from robots.txt."""
    parsed = urlparse(root_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    text = _get(robots_url)
    if not text:
        return []

    sitemaps = []
    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            loc = line.split(":", 1)[1].strip()
            if loc:
                sitemaps.append(loc)
    return sitemaps


def fetch_sitemap_urls(root_url: str) -> list[str]:
    """Return all URLs found in the site's sitemap(s).

    Checks robots.txt for Sitemap directives first, then tries common paths.
    Handles sitemap index files recursively. Returns deduplicated list.
    """
    parsed = urlparse(root_url)
    root_domain = parsed.netloc

    candidate_urls: list[str] = []

    # Priority 1: robots.txt Sitemap directives
    candidate_urls.extend(_sitemap_urls_from_robots(root_url))

    # Priority 2: common paths
    for path in _COMMON_PATHS:
        candidate_urls.append(urljoin(root_url, path))

    seen_sitemaps: set[str] = set()
    all_urls: list[str] = []

    for sitemap_url in candidate_urls:
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        xml_text = _get(sitemap_url)
        if xml_text:
            found = _parse_sitemap(xml_text, root_domain)
            if found:
                logger.info(f"Sitemap {sitemap_url} → {len(found)} URLs")
                all_urls.extend(found)
                break  # stop at first successful sitemap

    deduped = list(dict.fromkeys(all_urls))  # preserve order, remove dupes
    logger.info(f"[{root_domain}] sitemap total: {len(deduped)} URLs")
    return deduped
