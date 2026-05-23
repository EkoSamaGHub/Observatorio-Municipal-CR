from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import admin, documents, municipalities, reports, runs, search
from configs.constants import STALE_RUN_MINUTES
from configs.db import get_connection


def _reap_orphan_runs() -> None:
    """Close any crawl_runs left open by a previous crashed/killed worker."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, started_at, last_heartbeat FROM crawl_runs WHERE finished_at IS NULL"
        ).fetchall()
        reaped = 0
        for r in rows:
            ts = r.get("last_heartbeat") or r.get("started_at")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
            if age_min > STALE_RUN_MINUTES:
                conn.execute(
                    "UPDATE crawl_runs SET finished_at=%s, status=%s WHERE id=%s AND finished_at IS NULL",
                    (now, "abandoned", r["id"]),
                )
                reaped += 1
        conn.commit()
        conn.close()
        if reaped:
            print(f"[reaper] closed {reaped} orphan crawl_runs on startup")
    except Exception as e:
        print(f"[reaper] failed: {e}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _reap_orphan_runs()
    yield

app = FastAPI(
    title="MUNI84CR API",
    description="Costa Rica Municipal Intelligence Platform — 84 municipalities",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
