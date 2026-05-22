# Data Model

## Registry

### `municipalities.json`
Source of truth for all 84 municipalities. Loaded at pipeline start.

| Field | Type | Example |
|---|---|---|
| `id` | string | `SJ001` |
| `province` | string | `San José` |
| `name` | string | `Municipalidad de San José` |
| `root_url` | string | `https://www.msj.go.cr` |
| `active` | boolean | `true` |

ID scheme: two-letter province code + zero-padded index.

| Province | Code | Count |
|---|---|---|
| San José | SJ | 20 |
| Alajuela | AL | 16 |
| Heredia | HE | 10 |
| Guanacaste | GU | 11 |
| Puntarenas | PU | 13 |
| Cartago | CA | 8 |
| Limón | LI | 6 |

---

## Database Tables

### `pages`
One row per crawled URL. Updated on every crawl run.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `municipality_id` | TEXT | FK to registry |
| `url` | TEXT UNIQUE | Normalized URL |
| `content_type` | TEXT | From response headers or classifier |
| `content_hash` | TEXT | SHA-256 of `html_content` |
| `status_code` | INTEGER | HTTP status |
| `depth` | INTEGER | BFS depth from root |
| `last_crawled` | TEXT | UTC ISO-8601 timestamp |

### `documents`
One row per discovered document URL (PDF, DOCX, XLSX, ZIP, GIS).

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `municipality_id` | TEXT | |
| `url` | TEXT UNIQUE | |
| `file_type` | TEXT | `pdf`, `docx`, `xlsx`, `zip`, `gis` |
| `content_hash` | TEXT | Populated when downloaded |
| `downloaded` | INTEGER | 0/1 flag |
| `first_seen` | TEXT | UTC ISO-8601 |
| `last_seen` | TEXT | UTC ISO-8601 |

### `page_links`
Outgoing links per crawled page. Powers the discover-mode BFS seed so known pages are not re-fetched on subsequent runs.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `source_url` | TEXT | Page that contained the link |
| `target_url` | TEXT | Link destination (normalized) |
| UNIQUE | `(source_url, target_url)` | No duplicate edges |

### `page_diffs`
One row per detected content change. Written by `change_tracker.py` before the store step overwrites the hash.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `municipality_id` | TEXT | |
| `url` | TEXT | Page that changed |
| `old_hash` | TEXT | Previous SHA-256 |
| `new_hash` | TEXT | New SHA-256 |
| `detected_at` | TEXT | UTC ISO-8601 |

### `crawl_runs`
One row per pipeline execution. Used by the dashboard and for operational monitoring.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `started_at` | TEXT | UTC ISO-8601 |
| `finished_at` | TEXT | NULL while running |
| `municipalities` | INTEGER | Count processed |
| `pages_crawled` | INTEGER | Total fetched this run |
| `pages_changed` | INTEGER | Diffs detected |
| `pages_new` | INTEGER | First-time inserts |
| `errors` | INTEGER | Failed fetches |

---

## Document Classification

URLs are classified by `modules/classifiers.py` based on path pattern:

| Type | Pattern |
|---|---|
| `pdf` | `.pdf` in URL |
| `docx` | `.docx` in URL |
| `xlsx` | `.xlsx` in URL |
| `zip` | `.zip` in URL |
| `gis` | `arcgis` or `gis` in URL |
| `html` | everything else |

---

## CrawlResult (in-memory)

Intermediate dataclass produced by the crawler, consumed by the pipeline before DB write.

```python
@dataclass
class CrawlResult:
    url: str
    municipality_id: str
    status_code: int | None
    content_type: str
    content_hash: str
    html: str
    links: list[str]       # outgoing links → stored in page_links
    pdfs: list[str]        # discovered PDFs → stored in documents
    emails: list[str]      # discovered emails (not currently stored)
    depth: int
    error: str | None
```
