from datetime import datetime, timezone

from configs.db import get_connection
from crawlers.base import CrawlResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_changes(results: list[CrawlResult]) -> list[dict]:
    conn = get_connection()
    changes: list[dict] = []

    try:
        cursor = conn.cursor()

        for result in results:
            if not result.success:
                continue

            row = cursor.execute(
                "SELECT content_hash FROM pages WHERE url = %s", (result.url,)
            ).fetchone()

            if row is None:
                continue

            old_hash = row["content_hash"]
            new_hash = result.content_hash

            if old_hash and old_hash != new_hash:
                changes.append({
                    "municipality_id": result.municipality_id,
                    "url": result.url,
                    "old_hash": old_hash,
                    "new_hash": new_hash,
                    "detected_at": _now(),
                })

        if changes:
            cursor.executemany("""
                INSERT INTO page_diffs (municipality_id, url, old_hash, new_hash, detected_at)
                VALUES (%(municipality_id)s, %(url)s, %(old_hash)s, %(new_hash)s, %(detected_at)s)
            """, changes)
            conn.commit()

    finally:
        conn.close()

    return changes
