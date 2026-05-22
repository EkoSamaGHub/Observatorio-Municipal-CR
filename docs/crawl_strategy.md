# Crawl Strategy

## Approach

BFS (breadth-first search) within each municipality's root domain. The crawler stays within the same domain and respects configured depth and page limits.

## Two Modes

### `discover` (default)
Used when you want to find new pages.

1. Loads all known URLs for the municipality from the DB
2. Loads stored outgoing links from `page_links`
3. Marks known URLs as visited — they will not be re-fetched
4. Seeds the BFS queue with the stored links (edges of the known graph)
5. Fetches only URLs not yet in the DB

Result: zero duplicate fetches. Each run only touches pages not seen before.

### `monitor`
Used for frequent change detection on already-known pages.

1. Loads all known URLs from the DB
2. Re-fetches each one
3. Compares content hash — any change is written to `page_diffs`

Result: fast, targeted check. Does not discover new pages.

## Recommended Schedule

| Frequency | Command | Purpose |
|---|---|---|
| First run | `--depth 1 --max-pages 50 --mode discover` | Baseline across all 84 |
| Weekly | `--depth 2 --max-pages 200 --mode discover` | Extend coverage |
| Daily | `--mode monitor` | Change detection on known pages |

## Depth and Page Limits

- `--depth` controls how many BFS hops from the root URL
- `--max-pages` caps total fetches per municipality per run
- Depth 1 = homepage + direct links only (fast baseline)
- Depth 2 = one level deeper (discovers sub-sections)
- Depth 3+ = risks hitting thousands of pages on large sites

## URL Filtering

Before fetching, each URL is checked against:

1. **Scheme filter** — drops `mailto:`, `tel:`, `javascript:`, `data:`, `ftp:`
2. **Domain filter** — drops social media (Facebook, Twitter/X, Instagram, YouTube, LinkedIn, TikTok)
3. **Path filter** — drops SharePoint internals (`/_catalogs/`, `/_layouts/`, `/_vti_bin/`, `/_api/`), WordPress internals (`/wp-admin/`, `/wp-json/`)
4. **Extension filter** — drops binary files fetched as HTML: images, fonts, media, PDFs, Office docs, archives
5. **Domain boundary** — only follows links within the municipality's root domain
6. **robots.txt** — respects `Disallow` rules for `CostaRicaMunicipalResearchBot/1.0` (cached per domain)

## Request Behaviour

- User-agent: `CostaRicaMunicipalResearchBot/1.0`
- Default delay: 2 seconds between requests
- Retries: 3 attempts with exponential backoff (2s, 4s, 6s)
- Timeout: 30 seconds per request
- Scrapling handles stealthy headers automatically

## Link Graph Storage

Every outgoing link from a successfully crawled page is stored in `page_links`. This is what makes zero-duplication discover mode possible: on subsequent runs, the stored link graph seeds the BFS queue without needing to re-fetch the source pages.
