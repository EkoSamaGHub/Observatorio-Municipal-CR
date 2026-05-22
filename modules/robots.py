import urllib.request
import urllib.robotparser
from urllib.parse import urlparse
from functools import lru_cache

from configs.constants import USER_AGENT
from modules.logger import logger

_ROBOTS_TIMEOUT = 10  # seconds — prevents one slow server from stalling the crawl


@lru_cache(maxsize=128)
def _get_parser(robots_url: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        with urllib.request.urlopen(robots_url, timeout=_ROBOTS_TIMEOUT) as resp:
            rp.parse(resp.read().decode("utf-8", errors="replace").splitlines())
    except Exception as e:
        logger.warning(f"Could not fetch robots.txt at {robots_url}: {e}")
    return rp


def is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = _get_parser(robots_url)
    return rp.can_fetch(USER_AGENT, url)
