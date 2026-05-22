# Storage Strategy

## Environments

| Environment | Database | Location |
|---|---|---|
| Development | SQLite | `data/municipal.db` |
| Production | Postgres | Via `DATABASE_URL` environment variable |

The schema is identical in both environments. `configs/init_db.py` manages creation and `get_connection()` is the single entry point for all DB access.

## What Is Stored

### Pages
Every successfully crawled HTML page gets one row in `pages`. The row is upserted on every crawl run — `last_crawled` and `content_hash` are always kept current.

### Documents
PDF, DOCX, XLSX, ZIP, and GIS file URLs discovered during crawling are recorded in `documents`. The file is not downloaded by default (`downloaded = 0`). The `content_hash` field is populated only if the file is explicitly downloaded by a future pipeline step.

### Link Graph
All outgoing links from each crawled page are stored in `page_links`. This is not for display — it powers the zero-duplication discover mode. Without it, every run would re-fetch all known pages to find new ones.

### Diffs
Content changes are written to `page_diffs` before the store step overwrites the hash. This preserves the history of what changed and when.

### Crawl Runs
Each pipeline execution is recorded in `crawl_runs` with start/end times and aggregate stats. Used by the dashboard's last-updated display and for operational monitoring.

## What Is Not Stored

- Raw HTML is not persisted to the DB (too large). `storage.save_raw_html` in `settings.json` controls optional file-based HTML snapshots to `data/raw_html/`.
- Email addresses are currently extracted but not stored in the DB (future: contacts table).
- Full diff content (line-by-line diffs) is not stored — only hash pairs. Full diffs would require storing HTML snapshots.

## Upsert Strategy

All writes use `INSERT ... ON CONFLICT DO UPDATE` (SQLite) / `INSERT ... ON CONFLICT DO UPDATE` (Postgres). This makes every pipeline run idempotent — safe to re-run without duplicating data.

## Indexes

| Index | Table | Purpose |
|---|---|---|
| `idx_pages_municipality` | `pages` | Filter pages by municipality |
| `idx_documents_municipality` | `documents` | Filter docs by municipality |
| `idx_diffs_municipality` | `page_diffs` | Filter diffs by municipality |
| `idx_page_links_source` | `page_links` | Load outgoing links by source page |

## Migration Path to Postgres

1. Set `DATABASE_URL` environment variable to a Postgres connection string
2. Update `get_connection()` in `configs/init_db.py` to use `psycopg2` or `asyncpg`
3. Change `INSERT OR IGNORE` to `INSERT ... ON CONFLICT DO NOTHING` (already compatible)
4. Run `init_db()` against the Postgres instance to create the schema

No data model changes required — the schema was designed to be compatible with both.

## File-Based Outputs

In addition to the DB, the pipeline writes structured JSON summaries to `data/structured/{muni_id}.json` per municipality per run. These are useful for debugging and offline analysis without querying the DB.
