import urllib.request
import urllib.robotparser
from urllib.parse import urlparse
from functools import lru_cache

from configs.constants import USER_AGENT
from modules.logger import logger

_ROBOTS_TIMEOUT = 10  # seconds — prevents one slow server from stalling the crawl


@lru_cache(maxsize=128)
def _get_parser(robots_url: str) -> tuple:
    """Returns (RobotFileParser, was_fetched). Fail-open: if robots.txt
    can't be read (network error, SSL issue, 404, etc.) we treat the
    site as fully crawlable rather than blocking all discovery."""
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        with urllib.request.urlopen(robots_url, timeout=_ROBOTS_TIMEOUT) as resp:
            rp.parse(resp.read().decode("utf-8", errors="replace").splitlines())
        return rp, True
    except Exception as e:
        logger.warning(f"Could not fetch robots.txt at {robots_url}: {e}")
        return rp, False


def is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp, fetched = _get_parser(robots_url)
    if not fetched:
        return True  # fail-open: unreachable robots.txt → assume allowed
    return rp.can_fetch(USER_AGENT, url)
