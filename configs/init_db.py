import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "municipal.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        municipality_id TEXT    NOT NULL,
        url             TEXT    NOT NULL UNIQUE,
        content_type    TEXT,
        content_hash    TEXT,
        status_code     INTEGER,
        depth           INTEGER,
        last_crawled    TEXT    NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        municipality_id TEXT    NOT NULL,
        url             TEXT    NOT NULL UNIQUE,
        file_type       TEXT,
        content_hash    TEXT,
        downloaded      INTEGER DEFAULT 0,
        first_seen      TEXT    NOT NULL,
        last_seen       TEXT    NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS page_diffs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        municipality_id TEXT    NOT NULL,
        url             TEXT    NOT NULL,
        old_hash        TEXT,
        new_hash        TEXT,
        detected_at     TEXT    NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crawl_runs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at          TEXT    NOT NULL,
        finished_at         TEXT,
        municipalities      INTEGER DEFAULT 0,
        pages_crawled       INTEGER DEFAULT 0,
        pages_changed       INTEGER DEFAULT 0,
        pages_new           INTEGER DEFAULT 0,
        errors              INTEGER DEFAULT 0,
        sitemap_urls_found  INTEGER DEFAULT 0,
        completeness_pct    REAL    DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS page_links (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source_url  TEXT NOT NULL,
        target_url  TEXT NOT NULL,
        UNIQUE(source_url, target_url)
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_municipality ON pages(municipality_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_municipality ON documents(municipality_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diffs_municipality ON page_diffs(municipality_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_page_links_source ON page_links(source_url)")

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
