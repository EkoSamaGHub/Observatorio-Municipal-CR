import re
from datetime import datetime, timezone

from configs.db import get_connection
from crawlers.base import CrawlResult
from modules.classifiers import classify_url


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_title_and_snippet(html: str) -> tuple[str | None, str | None]:
    if not html:
        return None, None
    m = re.search(r"<title[^>]*>([^<]{1,200})</title>", html, re.IGNORECASE)
    title = m.group(1).strip() if m else None
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    snippet = text[:300] if text else None
    return title, snippet


def load_known_state(municipality_id: str) -> tuple[set[str], set[str]]:
    """Return (known_urls, seed_links) for a municipality from the DB.

    known_urls  — every URL already crawled; will be skipped in discover mode.
    seed_links  — all outgoing links stored from known pages; used to seed
                  the BFS queue so new pages reachable through known pages
                  are still discovered without re-fetching the known pages.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT url FROM pages WHERE municipality_id = %s", (municipality_id,)
        ).fetchall()
        known_urls = {r["url"] for r in rows}

        link_rows = conn.execute("""
            SELECT DISTINCT pl.target_url
            FROM page_links pl
            JOIN pages p ON p.url = pl.source_url
            WHERE p.municipality_id = %s
        """, (municipality_id,)).fetchall()
        seed_links = {r["target_url"] for r in link_rows}
    finally:
        conn.close()

    return known_urls, seed_links


def store_results(results: list[CrawlResult]) -> dict:
    conn = get_connection()
    stats = {"inserted": 0, "updated": 0, "docs_inserted": 0, "links_stored": 0}

    try:
        now = _now()
        cursor = conn.cursor()

        for result in results:
            if not result.success:
                continue

            title, snippet = _extract_title_and_snippet(result.html)

            cur = cursor.execute("""
                INSERT INTO pages (municipality_id, url, content_type, content_hash, status_code, depth, last_crawled, title, snippet)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(url) DO UPDATE SET
                    content_type  = EXCLUDED.content_type,
                    content_hash  = EXCLUDED.content_hash,
                    status_code   = EXCLUDED.status_code,
                    depth         = EXCLUDED.depth,
                    last_crawled  = EXCLUDED.last_crawled,
                    title         = EXCLUDED.title,
                    snippet       = EXCLUDED.snippet
                RETURNING id
            """, (
                result.municipality_id,
                result.url,
                result.content_type,
                result.content_hash,
                result.status_code,
                result.depth,
                now,
                title,
                snippet,
            ))
            stats["inserted"] += 1

            for target in result.links:
                cursor.execute("""
                    INSERT INTO page_links (source_url, target_url)
                    VALUES (%s, %s)
                    ON CONFLICT (source_url, target_url) DO NOTHING
                """, (result.url, target))
                stats["links_stored"] += 1

            for pdf_url in result.pdfs:
                cursor.execute("""
                    INSERT INTO documents (municipality_id, url, file_type, content_hash, first_seen, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(url) DO UPDATE SET last_seen = EXCLUDED.last_seen
                """, (
                    result.municipality_id,
                    pdf_url,
                    classify_url(pdf_url),
                    "",
                    now,
                    now,
                ))
                stats["docs_inserted"] += 1

        conn.commit()
    finally:
        conn.close()

    return stats
