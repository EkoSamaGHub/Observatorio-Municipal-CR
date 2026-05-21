import json
import time
from pathlib import Path

from configs.constants import MAX_DEPTH
from crawlers.scrapling_crawler import ScraplingCrawler
from modules.logger import logger


MUNICIPALITIES_FILE = Path("municipalities.json")
OUTPUT_DIR = Path("data/structured")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_municipalities(active_only: bool = True) -> list[dict]:
    with open(MUNICIPALITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [m for m in data if m["active"]] if active_only else data


def run(municipality_ids: list[str] | None = None, max_depth: int = MAX_DEPTH) -> None:
    municipalities = load_municipalities()

    if municipality_ids:
        municipalities = [m for m in municipalities if m["id"] in municipality_ids]

    crawler = ScraplingCrawler(request_delay=2.0, max_pages=1000)

    logger.info(f"Starting crawl: {len(municipalities)} municipalities, max_depth={max_depth}")

    for muni in municipalities:
        muni_id = muni["id"]
        name = muni["name"]
        url = muni["root_url"]

        logger.info(f"--- {name} ({muni_id}) ---")

        try:
            results = crawler.crawl(muni_id, url, max_depth=max_depth)

            summary = {
                "municipality_id": muni_id,
                "name": name,
                "root_url": url,
                "pages_crawled": len(results),
                "pages_ok": sum(1 for r in results if r.success),
                "pages_failed": sum(1 for r in results if not r.success),
                "total_pdfs": sum(len(r.pdfs) for r in results),
                "total_emails": sum(len(r.emails) for r in results),
                "pages": [
                    {
                        "url": r.url,
                        "depth": r.depth,
                        "status_code": r.status_code,
                        "content_type": r.content_type,
                        "content_hash": r.content_hash,
                        "pdfs": r.pdfs,
                        "emails": r.emails,
                        "error": r.error,
                    }
                    for r in results
                ],
            }

            out_file = OUTPUT_DIR / f"{muni_id.lower()}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            logger.info(f"{name}: {summary['pages_ok']} ok, {summary['pages_failed']} failed, {summary['total_pdfs']} PDFs")

        except Exception as e:
            logger.error(f"{name} ({muni_id}) crawl failed: {e}")

        time.sleep(2)


if __name__ == "__main__":
    run()
