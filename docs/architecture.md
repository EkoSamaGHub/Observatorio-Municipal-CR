# Architecture

## Overview

MUNI84CR is a full-stack municipal intelligence platform covering all 84 Costa Rican municipalities. It consists of three layers: a Python data pipeline, a FastAPI backend, and a Next.js public dashboard.

```
municipalities.json (registry)
        │
        ▼
┌───────────────────┐
│   Pipeline        │  pipeline.py — orchestrates all 7 steps
│   (Python)        │
│                   │
│  1. Crawl         │  crawlers/scrapling_crawler.py (Scrapling)
│  2. Extract       │  modules/classifiers.py
│  3. Normalize     │  modules/normalizer.py
│  4. Hash          │  modules/hashing.py
│  5. Store         │  modules/store.py → SQLite / Postgres
│  6. Diff          │  modules/change_tracker.py
│  7. Monitor       │  modules/monitoring.py (planned)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   SQLite (dev)    │  data/municipal.db
│   Postgres (prod) │
│                   │
│  pages            │
│  documents        │
│  page_links       │
│  page_diffs       │
│  crawl_runs       │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   FastAPI         │  api/main.py
│   (Python)        │
│                   │
│  /municipalities  │
│  /documents       │
│  /search          │
│  /runs            │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   Next.js         │  frontend/
│   (Vercel)        │
│                   │
│  Inicio           │
│  Municipalidades  │
│  Documentos       │
│  Cambios          │
│  Búsqueda         │
└───────────────────┘
```

## Layer Responsibilities

### Pipeline (`pipeline.py`)
Orchestrates the 7-step crawl cycle. Accepts CLI flags for mode, depth, page limits, and municipality filters. Writes run metadata to `crawl_runs`.

### Crawler (`crawlers/`)
- `base.py` — abstract `BaseCrawler` interface and `CrawlResult` dataclass
- `scrapling_crawler.py` — Scrapling-based implementation; BFS within a single domain
- `crawl_all.py` — loads the municipality registry and coordinates per-municipality crawls

Two crawl modes:
- **discover** — skips known URLs, seeds BFS from stored link graph, finds new pages
- **monitor** — re-fetches only known URLs, checks for content changes

### Modules (`modules/`)
| Module | Role |
|---|---|
| `url_manager.py` | URL normalization, scheme/domain/path filtering |
| `classifiers.py` | Content type classification by URL pattern |
| `hashing.py` | SHA-256 content fingerprinting |
| `normalizer.py` | Post-crawl normalization of results |
| `store.py` | DB upserts for pages, documents, link graph |
| `change_tracker.py` | Hash comparison and diff recording |
| `robots.py` | Per-domain robots.txt enforcement (cached) |
| `retry_manager.py` | Exponential backoff retry wrapper |
| `logger.py` | Centralized structured logging |

### API (`api/`)
FastAPI application with read-only endpoints. All responses are JSON. CORS enabled for the frontend. DB connection injected via `deps.py`.

### Frontend (`frontend/`)
Next.js App Router application deployed to Vercel. All public-facing text is in Spanish via `next-intl`. Consumes the FastAPI via `lib/api.ts`. Environment-based API URL via `NEXT_PUBLIC_API_URL`.

## Language Convention

| Scope | Language |
|---|---|
| Code, variables, comments, logs, DB schema | English |
| All public-facing UI text | Spanish (Costa Rican) |
| i18n strings | `frontend/messages/es.json` |

## Dependency on Scrapling

Scrapling (`github.com/D4Vinci/Scrapling`) is used as an external dependency for HTTP fetching and CSS/XPath element selection. The crawler is abstracted behind `BaseCrawler` so Scrapling can be swapped or extended into broader projects without touching the pipeline.

## Database Strategy

- **Development:** SQLite at `data/municipal.db`
- **Production:** Postgres (connection string via environment variable)
- Schema is managed in `configs/init_db.py`; `get_connection()` is the single entry point

## Deployment

| Component | Target |
|---|---|
| Pipeline | Run locally or on a scheduled VPS job |
| FastAPI | Any WSGI/ASGI host (Railway, Render, VPS) |
| Next.js | Vercel |
