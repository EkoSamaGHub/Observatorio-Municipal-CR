# Roadmap

## MVP (current)

- [x] Municipality registry — all 84 municipalities with provinces and URLs
- [x] Web crawler — Scrapling-based BFS, depth/page limits, robots.txt, path filtering
- [x] Two crawl modes — `discover` (zero duplication) and `monitor` (change detection)
- [x] Link graph storage — powers incremental crawls without re-fetching known pages
- [x] 7-step pipeline — Crawl → Extract → Normalize → Hash → Store → Diff → Monitor
- [x] SQLite (dev) with migration path to Postgres (prod)
- [x] FastAPI layer — municipalities, documents, diffs, runs, search endpoints
- [x] Next.js dashboard — Spanish UI, next-intl i18n, Vercel deployment
- [x] Public pages — Inicio, Municipalidades, Perfil Municipal, Documentos, Cambios, Búsqueda

## Phase 2 — Intelligence

- [ ] SICOP integration — scrape national procurement system for licitaciones
- [ ] Entity extraction — pull amounts, companies, officials, dates from page text
- [ ] PDF engine — download and extract text from discovered PDFs
- [ ] GIS detector — identify and catalogue ArcGIS layers, KML, shapefiles
- [ ] Document classifier — tag documents by category (acta, presupuesto, contrato, etc.)
- [ ] Anomaly detection — flag unusual procurement patterns or sudden document changes

## Phase 2 — Alerts & Users

- [ ] Alert subscriptions — follow a municipality or document category
- [ ] Email delivery — notify on new procurement, changed pages, new documents
- [ ] Webhook support — POST alerts to external systems
- [ ] Slack / WhatsApp integration
- [ ] Dashboard authentication — user accounts for alert management

## Phase 2 — Dashboard

- [ ] GIS browser — interactive map of cartographic layers per municipality
- [ ] Licitaciones page — procurement search across all municipalities
- [ ] Transparencia scoring — compliance index based on published documents
- [ ] Download / export — CSV and JSON export from the dashboard
- [ ] Timeline view — visual history of changes per municipality

## Phase 3 — Scale

- [ ] Migrate to Postgres
- [ ] Async pipeline — concurrent crawling across municipalities
- [ ] Full-text search index — Elasticsearch or Postgres FTS
- [ ] Scrapling integration — extend into broader multi-project scraping platform
- [ ] API v2 — pagination, filtering, sorting on all endpoints
- [ ] Scheduled pipeline — cron-based daily monitor + weekly discover runs
- [ ] CI/CD — automated tests and deployment pipeline

## Deferred

These were explicitly scoped out of MVP:

- SICOP integration
- Alerts delivery (email, webhook, Slack, WhatsApp)
- Dashboard authentication / user accounts
- AI features (entity extraction, anomaly detection)
