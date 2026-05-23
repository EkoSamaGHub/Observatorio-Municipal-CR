import argparse
from datetime import datetime, timezone

from configs.db import get_connection
from configs.init_db import init_db
from crawlers.crawl_all import load_municipalities
from crawlers.scrapling_crawler import ScraplingCrawler
from modules.change_tracker import detect_changes
from modules.classifiers import classify_url
from modules.logger import logger
from modules.normalizer import normalize_results
from modules.sitemap import fetch_sitemap_urls
from modules.store import load_known_state, store_results


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_pipeline(
    municipality_ids: list[str] | None = None,
    max_depth: int = 2,
    request_delay: float = 2.0,
    max_pages: int = 1000,
    mode: str = "discover",
    only_missing: bool = False,
) -> None:
    """
    mode="discover"  — find new/updated pages on all (or selected) municipalities.
    mode="monitor"   — re-check known pages for content changes (watchdog).
    only_missing     — discover mode only: skip municipalities that already have
                       pages in the DB; focus on the ones not yet indexed.
    """
    if mode not in ("discover", "monitor"):
        raise ValueError("mode must be 'discover' or 'monitor'")

    init_db()
    conn = get_connection()
    run_id = conn.execute(
        "INSERT INTO crawl_runs (started_at) VALUES (%s) RETURNING id", (_now(),)
    ).lastrowid
    conn.commit()
    conn.close()

    def _close_run():
        try:
            c = get_connection()
            c.execute(
                "UPDATE crawl_runs SET finished_at=%s WHERE id=%s AND finished_at IS NULL",
                (_now(), run_id),
            )
            c.commit()
            c.close()
        except Exception:
            pass

    import atexit
    atexit.register(_close_run)

    municipalities = load_municipalities()
    if municipality_ids:
        municipalities = [m for m in municipalities if m["id"] in municipality_ids]

    # In monitor mode: only process municipalities that already have pages.
    # In discover + only_missing: skip municipalities already indexed.
    if mode == "monitor" or only_missing:
        conn = get_connection()
        indexed = {
            r["municipality_id"]
            for r in conn.execute(
                "SELECT DISTINCT municipality_id FROM pages"
            ).fetchall()
        }
        conn.close()
        if mode == "monitor":
            municipalities = [m for m in municipalities if m["id"] in indexed]
            logger.info(f"Monitor mode: {len(municipalities)} municipalities with known pages")
        elif only_missing:
            municipalities = [m for m in municipalities if m["id"] not in indexed]
            logger.info(f"Discover (only-missing): {len(municipalities)} unindexed municipalities")

    crawler = ScraplingCrawler(
        request_delay=request_delay,
        max_pages=max_pages,
        respect_robots=True,
        verify_ssl=False,   # many .go.cr sites have self-signed or mismatched certs
    )

    total_pages = 0
    total_changed = 0
    total_new = 0
    total_errors = 0
    total_sitemap_urls = 0

    logger.info(f"Pipeline started — run_id={run_id} mode={mode} municipalities={len(municipalities)}")

    for muni in municipalities:
        muni_id = muni["id"]
        name = muni["name"]
        logger.info(f"=== {name} ({muni_id}) ===")

        try:
            stats = crawl_one_municipality(muni, crawler, mode, max_depth, max_pages)
            total_pages += stats["pages"]
            total_new += stats["new"]
            total_changed += stats["changed"]
            total_errors += stats["errors"]
            total_sitemap_urls += stats["sitemap_total"]
            logger.info(
                f"{name}: fetched={stats['fetched']} new={stats['new']} "
                f"changed={stats['changed']} sitemap={stats['sitemap_total']} "
                f"completeness={stats['completeness']:.1f}% errors={stats['errors']} "
                f"terminated_by={stats['terminated_by']}"
            )
        except Exception as e:
            # One bad municipality must never abort the whole pass.
            total_errors += 1
            logger.error(f"[{muni_id}] crawl failed, skipping: {e}")

    # ── Finalize run record ──────────────────────────────────────────────────
    conn = get_connection()
    conn.execute("""
        UPDATE crawl_runs
        SET finished_at=%s, status='done', municipalities=%s, pages_crawled=%s, pages_changed=%s,
            pages_new=%s, errors=%s, sitemap_urls_found=%s
        WHERE id=%s
    """, (
        _now(), len(municipalities), total_pages, total_changed,
        total_new, total_errors, total_sitemap_urls, run_id,
    ))
    conn.commit()
    conn.close()

    logger.info(
        f"Pipeline complete — run_id={run_id} mode={mode} | "
        f"municipalities={len(municipalities)} pages={total_pages} "
        f"new={total_new} changed={total_changed} "
        f"sitemap_urls={total_sitemap_urls} errors={total_errors}"
    )


def crawl_one_municipality(muni: dict, crawler, mode: str, max_depth: int,
                           max_pages: int = 1000, on_progress=None) -> dict:
    """Crawl + index a single municipality with bounded memory.

    Pages are stored incrementally per batch over one shared DB connection;
    `html` is released after each batch instead of buffering the whole site.
    `on_progress(pages_so_far)` is called after each batch (used for heartbeats).
    Returns aggregate stats. Raising propagates to the caller.
    """
    muni_id = muni["id"]
    root_url = muni["root_url"]
    stats = {"pages": 0, "new": 0, "changed": 0, "errors": 0,
             "sitemap_total": 0, "completeness": 0.0, "fetched": 0,
             "terminated_by": "complete"}

    conn = get_connection()
    try:
        known_urls, seed_links = load_known_state(muni_id, conn=conn)
        logger.info(f"[{muni_id}] known={len(known_urls)} seed_links={len(seed_links)}")

        sitemap_urls: list[str] = fetch_sitemap_urls(root_url) if mode == "discover" else []
        stats["sitemap_total"] = len(sitemap_urls)

        def sink(batch):
            for r in batch:
                if not r.content_type:
                    r.content_type = classify_url(r.url)
            results = normalize_results(batch)
            changes = detect_changes(results, conn=conn)
            store_stats = store_results(results, conn=conn)
            stats["pages"] += len(results)
            stats["new"] += store_stats["inserted"]
            stats["changed"] += len(changes)
            stats["errors"] += sum(1 for r in results if not r.success)
            if on_progress:
                on_progress(stats["pages"])

        summary = crawler.crawl(
            muni_id, root_url, max_depth=max_depth, mode=mode,
            known_urls=known_urls, seed_links=seed_links, sitemap_urls=sitemap_urls,
            on_batch=sink,
        )
        stats["terminated_by"] = summary.terminated_by
        stats["completeness"] = summary.completeness_pct
        stats["fetched"] = summary.pages_fetched
        if summary.terminated_by == "max_pages":
            logger.warning(f"[{muni_id}] hit max_pages ({max_pages}); site may have more pages")
        return stats
    finally:
        conn.close()


def select_municipality_ids(mode: str, only_missing: bool = False,
                            ids: list[str] | None = None) -> list[str]:
    """Resolve which municipality IDs a run should cover, applying the same
    discover/monitor/only-missing filtering the legacy pipeline used."""
    municipalities = load_municipalities()
    if ids:
        municipalities = [m for m in municipalities if m["id"] in ids]

    if mode == "monitor" or only_missing:
        conn = get_connection()
        try:
            indexed = {
                r["municipality_id"]
                for r in conn.execute("SELECT DISTINCT municipality_id FROM pages").fetchall()
            }
        finally:
            conn.close()
        if mode == "monitor":
            municipalities = [m for m in municipalities if m["id"] in indexed]
        elif only_missing:
            municipalities = [m for m in municipalities if m["id"] not in indexed]

    return [m["id"] for m in municipalities]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MUNI84CR Pipeline")
    parser.add_argument("--ids", nargs="*", help="Municipality IDs to crawl (default: all)")
    parser.add_argument("--depth", type=int, default=2, help="Max crawl depth (default: 2)")
    parser.add_argument("--delay", type=float, default=1.0, help="Request delay in seconds (default: 1.0)")
    parser.add_argument("--max-pages", type=int, default=1000, help="Max pages per site (default: 1000)")
    parser.add_argument(
        "--mode",
        choices=["discover", "monitor"],
        default="discover",
        help=(
            "discover: crawl and index new pages across all municipalities. "
            "monitor: re-check only already-indexed pages for content changes (watchdog)."
        ),
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="discover mode only: skip municipalities already in the DB; index the remaining ones first.",
    )
    args = parser.parse_args()

    run_pipeline(
        municipality_ids=args.ids,
        max_depth=args.depth,
        request_delay=args.delay,
        max_pages=args.max_pages,
        mode=args.mode,
        only_missing=args.only_missing,
    )
