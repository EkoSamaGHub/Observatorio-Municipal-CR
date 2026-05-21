from crawlers.base import CrawlResult
from modules.url_manager import normalize_url


def normalize_result(result: CrawlResult) -> CrawlResult:
    result.url = normalize_url(result.url)
    result.links = [normalize_url(l) for l in result.links]
    result.pdfs = [normalize_url(p) for p in result.pdfs]
    result.emails = [e.lower().strip() for e in result.emails]
    return result


def normalize_results(results: list[CrawlResult]) -> list[CrawlResult]:
    return [normalize_result(r) for r in results]
