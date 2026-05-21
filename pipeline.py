import argparse
from datetime import datetime, timezone

from configs.init_db import get_connection, init_db
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
) -> None:

    if mode not in ("discover", "monitor"):
        raise ValueError("mode must be 'discover' or 'monitor'")

    init_db()
    conn = get_connection()
    run_id = conn.execute(
        "INSERT INTO crawl_runs (started_at) VALUES (?)", (_now(),)
    ).lastrowid
    conn.commit()
    conn.close()

    municipalities = load_municipalities()
    if municipality_ids:
        municipalities = [m for m in municipalities if m["id"] in municipality_ids]

    crawler = ScraplingCrawler(
        request_delay=request_delay,
        max_pages=max_pages,
        respect_robots=True,
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
        root_url = muni["root_url"]

        logger.info(f"=== {name} ({muni_id}) ===")

        # ── Load known state ─────────────────────────────────────────────────
        known_urls, seed_links = load_known_state(muni_id)
        logger.info(f"[{muni_id}] known={len(known_urls)} seed_links={len(seed_links)}")

        # ── Fetch sitemap ────────────────────────────────────────────────────
        sitemap_urls: list[str] = []
        if mode == "discover":
            sitemap_urls = fetch_sitemap_urls(root_url)
            total_sitemap_urls += len(sitemap_urls)

        # ── Step 1: Crawl ────────────────────────────────────────────────────
        logger.info(f"Step 1: Crawl [{mode}]")
        summary = crawler.crawl(
            muni_id,
            root_url,
            max_depth=max_depth,
            mode=mode,
            known_urls=known_urls,
            seed_links=seed_links,
            sitemap_urls=sitemap_urls,
        )

        raw_results = summary.results

        if not raw_results:
            logger.info(f"{name}: nothing to crawl")
            continue

        # Warn if truncated
        if summary.terminated_by == "max_pages":
            logger.warning(
                f"[{muni_id}] hit max_pages limit ({max_pages}) — "
                f"site may have more pages. Run again to continue discovery."
            )

        if summary.sitemap_total > 0:
            logger.info(
                f"[{muni_id}] completeness: {summary.pages_fetched}/{summary.sitemap_total} "
                f"sitemap URLs = {summary.completeness_pct:.1f}%"
            )

        # ── Step 2: Extract ──────────────────────────────────────────────────
        logger.info("Step 2: Extract")
        for result in raw_results:
            if not result.content_type:
                result.content_type = classify_url(result.url)

        # ── Step 3: Normalize ────────────────────────────────────────────────
        logger.info("Step 3: Normalize")
        results = normalize_results(raw_results)

        # ── Step 4: Hash (done inside CrawlResult) ───────────────────────────
        logger.info("Step 4: Hash — verified")

        # ── Step 5: Diff + Store ─────────────────────────────────────────────
        logger.info("Step 5: Store")
        changes = detect_changes(results)
        store_stats = store_results(results)

        errors = sum(1 for r in results if not r.success)
        new_pages = store_stats["inserted"]
        changed_pages = len(changes)

        total_pages += len(results)
        total_new += new_pages
        total_changed += changed_pages
        total_errors += errors

        # ── Step 6: Diff report ──────────────────────────────────────────────
        logger.info(f"Step 6: Diff — {changed_pages} changes detected")
        for change in changes:
            logger.info(f"  CHANGED: {change['url']}")

        # ── Step 7: Monitor ──────────────────────────────────────────────────
        logger.info(
            f"Step 7: Monitor — new={new_pages} changed={changed_pages} "
            f"terminated_by={summary.terminated_by} errors={errors}"
        )
        logger.info(
            f"{name}: crawled={len(results)} new={new_pages} changed={changed_pages} "
            f"pdfs={store_stats['docs_inserted']} links={store_stats['links_stored']} "
            f"sitemap={summary.sitemap_total} completeness={summary.completeness_pct:.1f}% errors={errors}"
        )

    # ── Finalize run record ──────────────────────────────────────────────────
    conn = get_connection()
    conn.execute("""
        UPDATE crawl_runs
        SET finished_at=?, municipalities=?, pages_crawled=?, pages_changed=?,
            pages_new=?, errors=?, sitemap_urls_found=?
        WHERE id=?
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
        help="discover: find new pages. monitor: re-check known pages only.",
    )
    args = parser.parse_args()

    run_pipeline(
        municipality_ids=args.ids,
        max_depth=args.depth,
        request_delay=args.delay,
        max_pages=args.max_pages,
        mode=args.mode,
    )
