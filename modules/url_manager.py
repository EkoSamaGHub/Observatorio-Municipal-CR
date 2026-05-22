import re
from urllib.parse import urlparse, urlunparse


IGNORED_SCHEMES = [
    "mailto",
    "tel",
    "javascript",
    "data",
    "ftp",
]

IGNORED_DOMAINS = [
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "linkedin.com",
    "tiktok.com",
    "whatsapp.com",
    "t.me",
]

# SharePoint / CMS internals that are never public content
IGNORED_PATH_PREFIXES = [
    "/_catalogs/",
    "/_layouts/",
    "/_vti_bin/",
    "/_vti_pvt/",
    "/_api/",
    "/_forms/",
    "/_controltemplates/",
    "/wp-admin/",
    "/wp-login",
    "/wp-json/",
    "/xmlrpc.php",
    "/feed/",
    "/wp-content/plugins/",
    "/wp-content/themes/",
    "/wp-content/uploads/",
    "/tag/",
    "/category/",
    "/author/",
]

# WordPress pagination: /page/2, /page/3, …
_WP_PAGE_RE = re.compile(r"/page/\d+")

# WordPress query-string archive params
_IGNORED_QUERY_PARAMS = {"p", "cat", "tag", "m", "paged"}



def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(fragment="")
    normalized = urlunparse(clean)
    if normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def should_ignore(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.scheme in IGNORED_SCHEMES:
        return True

    for domain in IGNORED_DOMAINS:
        if domain in parsed.netloc:
            return True

    path_lower = parsed.path.lower()
    for prefix in IGNORED_PATH_PREFIXES:
        if path_lower.startswith(prefix):
            return True

    if _WP_PAGE_RE.search(path_lower):
        return True

    if parsed.query:
        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)
        if _IGNORED_QUERY_PARAMS.intersection(params):
            return True

    return False
