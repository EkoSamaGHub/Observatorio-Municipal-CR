"""Cloudflare-bypass fetch path.

Some municipal sites sit behind Cloudflare's managed challenge ("Just a
moment..." interstitial). The plain `scrapling.fetchers.Fetcher` is a stateless
HTTP client, so it gets a 403 page containing the JS challenge instead of the
real site. `StealthyFetcher` drives a headless Chromium that can solve the
challenge.

This module is the narrow entry point: detect the challenge on a normal
response, and re-fetch via stealth only when needed. The per-host decision is
memoized in-process so subsequent URLs on a known-CF host skip the wasted
plain-HTTP attempt.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from modules.logger import logger


_CF_BODY_MARKERS = (
    "challenges.cloudflare.com",
    "__cf_chl_",
    "cf-chl-",
    "Just a moment",
    "cf-mitigated",
)

# Per-process memo: hosts that previously needed the stealth path. Populated on
# first CF detection; consulted before each plain fetch so we go straight to
# stealth on subsequent URLs of the same site within the worker.
_cf_required_hosts: set[str] = set()


def host_requires_stealth(url: str) -> bool:
    return urlparse(url).netloc in _cf_required_hosts


def mark_host_requires_stealth(url: str) -> None:
    host = urlparse(url).netloc
    if host and host not in _cf_required_hosts:
        logger.info(f"stealth: marking {host} as Cloudflare-protected (will use headless Chromium)")
        _cf_required_hosts.add(host)


def looks_like_cf_challenge(status: Optional[int], body: str) -> bool:
    """Heuristic — CF managed challenge typically returns 403 or 503 with a
    distinctive challenge-platform body. False positives are tolerable (we just
    do one extra stealth fetch); false negatives leave the site uncrawled."""
    if status not in (403, 503):
        return False
    if not body:
        return False
    snippet = body[:4000]
    return any(m in snippet for m in _CF_BODY_MARKERS)


def stealth_fetch(url: str, user_agent: str, timeout_seconds: int = 60):
    """Fetch via headless Chromium and solve any CF challenge in the way.

    Returns a Scrapling Response-compatible object on success, or None when
    Playwright/Chromium is unavailable. Raises on transport/timeout errors so
    the caller can record an error in the CrawlResult.
    """
    try:
        from scrapling.fetchers import StealthyFetcher  # type: ignore
    except Exception as e:
        logger.warning(f"stealth: StealthyFetcher import failed ({e}); cannot bypass Cloudflare")
        return None

    try:
        return StealthyFetcher.fetch(
            url,
            headless=True,
            solve_cloudflare=True,
            disable_resources=True,
            network_idle=True,
            useragent=user_agent,
            timeout=timeout_seconds * 1000,
        )
    except Exception as e:
        msg = str(e).lower()
        if "executable doesn" in msg or "playwright" in msg or "chromium" in msg:
            logger.warning(
                f"stealth: Chromium not installed in this environment ({e}); "
                "run `playwright install chromium` to enable CF bypass"
            )
            return None
        raise
