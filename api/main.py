from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import documents, municipalities, runs, search

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
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(municipalities.router)
app.include_router(documents.router)
app.include_router(runs.router)
app.include_router(search.router)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "platform": "MUNI84CR", "version": "0.1.0"}
