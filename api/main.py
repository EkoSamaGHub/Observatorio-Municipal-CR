from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import admin, documents, municipalities, reports, runs, search

app = FastAPI(
    title="MUNI84CR API",
    description="Costa Rica Municipal Intelligence Platform — 84 municipalities",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # GET for the public read API; POST drives the token-authenticated admin
    # control plane. Auth is a bearer token (not cookies), so a wildcard origin
    # without credentials is safe.
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(municipalities.router)
app.include_router(documents.router)
app.include_router(runs.router)
app.include_router(search.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.on_event("startup")
def _ensure_schema() -> None:
    # Idempotent: makes sure admin tables (e.g. crawl_events) exist even on a
    # fresh API deploy that boots before any crawl worker has run init_db.
    # Best-effort — a transient DB hiccup must not stop the API serving reads.
    try:
        from configs.init_db import init_db
        init_db()
    except Exception as e:  # noqa: BLE001
        print(f"[api] startup init_db skipped: {e}", flush=True)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "platform": "MUNI84CR", "version": "0.1.0"}
