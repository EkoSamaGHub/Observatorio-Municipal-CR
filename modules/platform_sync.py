"""
Sync crawler-platform Page results into Observatory's pages / documents tables.

The platform returns Page objects after each crawl job completes.
This module maps them to the Observatory's existing schema and detects
content changes for the page_diffs table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from modules.logger import logger

# MIME types that route to the documents table instead of pages
_DOC_MIME: frozenset[str] = frozenset({
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/x-zip-compressed",
})

_EXT_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "docx",
    ".xls": "xls",
    ".xlsx": "xlsx",
    ".ppt": "ppt",
    ".pptx": "pptx",
    ".zip": "zip",
}


def _file_type(url: str, content_type: str) -> str | None:
    """Return a short file_type string if the URL is a downloadable document."""
    path = urlparse(url).path.lower().split("?")[0]
    for ext, ft in _EXT_MAP.items():
        if path.endswith(ext):
            return ft
    ct = (content_type or "").split(";")[0].strip()
    if ct in _DOC_MIME:
        # e.g. "application/pdf" → "pdf", "application/vnd...docx" → "docx"
        return ct.split("/")[-1].split(".")[-1]
    return None


def _depth(url: str, root_url: str) -> int:
    """Estimate path depth relative to municipality root URL."""
    try:
        path = urlparse(url).path.rstrip("/")
        root = urlparse(root_url).path.rstrip("/")
        rel = path[len(root):] if path.startswith(root) else path
        return len([s for s in rel.split("/") if s])
    except Exception:
        return 0


def sync_job(
    job_id: str,
    municipality_id: str,
    root_url: str,
    pages: list[dict],
    conn,
) -> dict:
    """
    Upsert platform Page records into Observatory's pages / documents tables.
    Writes page_diffs rows when content_hash changes.
    Returns stats: {pages, documents, new, changed, errors}.
    """
    now = datetime.now(timezone.utc).isoformat()
    stats: dict[str, int] = {
        "pages": 0,
        "documents": 0,
        "new": 0,
        "changed": 0,
        "errors": 0,
    }

    # Snapshot existing pages so we can detect new vs changed
    cur = conn.execute(
        "SELECT url, content_hash FROM pages WHERE municipality_id = %s",
        (municipality_id,),
    )
    known: dict[str, str] = {r["url"]: (r["content_hash"] or "") for r in cur.fetchall()}

    for p in pages:
        url = p.get("finalUrl") or p.get("url", "")
        if not url:
            continue

        ct = (p.get("contentType") or "text/html").split(";")[0].strip()
        status_code = p.get("httpStatus") or 200
        content_hash = p.get("contentHash") or ""
        title = (p.get("title") or "")[:500]
        snippet = (p.get("description") or "")[:300]
        fetched_at = p.get("fetchedAt") or now

        try:
            ft = _file_type(url, ct)
            if ft:
                conn.execute(
                    """
                    INSERT INTO documents
                        (municipality_id, url, file_type, content_hash,
                         downloaded, first_seen, last_seen)
                    VALUES (%s, %s, %s, %s, false, %s, %s)
                    ON CONFLICT (url) DO UPDATE
                      SET content_hash = EXCLUDED.content_hash,
                          last_seen    = EXCLUDED.last_seen
                    """,
                    (municipality_id, url, ft, content_hash, fetched_at, fetched_at),
                )
                stats["documents"] += 1
            else:
                depth = _depth(url, root_url)
                is_new = url not in known
                prev_hash = known.get(url, "")
                changed = (
                    not is_new
                    and bool(prev_hash)
                    and bool(content_hash)
                    and prev_hash != content_hash
                )

                conn.execute(
                    """
                    INSERT INTO pages
                        (municipality_id, url, content_type, content_hash,
                         status_code, depth, last_crawled, title, snippet)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE
                      SET content_type = EXCLUDED.content_type,
                          content_hash = EXCLUDED.content_hash,
                          status_code  = EXCLUDED.status_code,
                          depth        = EXCLUDED.depth,
                          last_crawled = EXCLUDED.last_crawled,
                          title        = EXCLUDED.title,
                          snippet      = EXCLUDED.snippet
                    """,
                    (municipality_id, url, ct, content_hash,
                     status_code, depth, fetched_at, title, snippet),
                )
                if changed:
                    conn.execute(
                        """
                        INSERT INTO page_diffs
                            (municipality_id, url, old_hash, new_hash, detected_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (municipality_id, url, prev_hash, content_hash, now),
                    )
                    stats["changed"] += 1
                elif is_new:
                    stats["new"] += 1
                stats["pages"] += 1

        except Exception as e:
            logger.error(f"[sync] {municipality_id} {url}: {e}")
            stats["errors"] += 1

    conn.commit()
    return stats
