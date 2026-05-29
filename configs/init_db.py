from configs.db import get_connection, BACKEND

_DB_PATH_MSG = "TigerData cloud (Postgres)" if BACKEND == "postgres" else "local SQLite"

# Stable 64-bit key for the init-db Postgres advisory lock. Hex spells "MUNI84CR"
# in a derived form; what matters is that every worker in the system uses the
# same constant so they serialize. Without serialization, concurrent
# CREATE TABLE IF NOT EXISTS / ALTER TABLE IF NOT EXISTS take system-catalog
# locks that deadlock under N>=3 concurrent workers, killing the work step at
# startup with psycopg.errors.DeadlockDetected.
_INIT_LOCK_KEY = 0x4D554E49_38344352  # bigint, fits in Postgres advisory-lock arg


def _exec(conn, sql: str) -> None:
    conn.execute(sql)


def init_db() -> None:
    conn = get_connection()
    try:
        if BACKEND == "postgres":
            conn.execute("SELECT pg_advisory_lock(%s)", (_INIT_LOCK_KEY,))
            try:
                _init_postgres(conn)
                _migrate_postgres(conn)
            finally:
                conn.execute("SELECT pg_advisory_unlock(%s)", (_INIT_LOCK_KEY,))
        else:
            _init_sqlite(conn)
            _migrate_sqlite(conn)
        conn.commit()
    finally:
        conn.close()
    print(f"Database initialized — backend: {_DB_PATH_MSG}")


def _migrate_sqlite(conn) -> None:
    existing_pages = {r["name"] for r in conn.execute("PRAGMA table_info(pages)").fetchall()}
    for col, typedef in [("title", "TEXT"), ("snippet", "TEXT")]:
        if col not in existing_pages:
            conn.execute(f"ALTER TABLE pages ADD COLUMN {col} {typedef}")
            print(f"  migration: pages.{col} added")

    existing_runs = {r["name"] for r in conn.execute("PRAGMA table_info(crawl_runs)").fetchall()}
    for col, typedef in [
        ("sitemap_urls_found", "INTEGER DEFAULT 0"),
        ("completeness_pct", "REAL DEFAULT 0"),
        ("status", "TEXT DEFAULT 'running'"),
        ("worker_id", "TEXT"),
        ("last_heartbeat", "TEXT"),
        ("mode", "TEXT DEFAULT 'discover'"),
    ]:
        if col not in existing_runs:
            conn.execute(f"ALTER TABLE crawl_runs ADD COLUMN {col} {typedef}")
            print(f"  migration: crawl_runs.{col} added")


def _migrate_postgres(conn) -> None:
    conn.execute("ALTER TABLE pages ADD COLUMN IF NOT EXISTS title TEXT")
    conn.execute("ALTER TABLE pages ADD COLUMN IF NOT EXISTS snippet TEXT")
    conn.execute("ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS sitemap_urls_found INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS completeness_pct REAL DEFAULT 0")
    conn.execute("ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'running'")
    conn.execute("ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS worker_id TEXT")
    conn.execute("ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS last_heartbeat TEXT")
    conn.execute("ALTER TABLE crawl_runs ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'discover'")


def _init_sqlite(conn) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        municipality_id TEXT    NOT NULL,
        url             TEXT    NOT NULL UNIQUE,
        content_type    TEXT,
        content_hash    TEXT,
        status_code     INTEGER,
        depth           INTEGER,
        last_crawled    TEXT    NOT NULL,
        title           TEXT,
        snippet         TEXT
    )
    """)

    conn.execute("""
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

    conn.execute("""
    CREATE TABLE IF NOT EXISTS page_diffs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        municipality_id TEXT    NOT NULL,
        url             TEXT    NOT NULL,
        old_hash        TEXT,
        new_hash        TEXT,
        detected_at     TEXT    NOT NULL
    )
    """)

    conn.execute("""
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

    conn.execute("""
    CREATE TABLE IF NOT EXISTS page_links (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source_url  TEXT NOT NULL,
        target_url  TEXT NOT NULL,
        UNIQUE(source_url, target_url)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS crawl_tasks (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id            INTEGER NOT NULL,
        municipality_id   TEXT    NOT NULL,
        mode              TEXT    NOT NULL DEFAULT 'discover',
        status            TEXT    NOT NULL DEFAULT 'pending',
        attempts          INTEGER NOT NULL DEFAULT 0,
        max_attempts      INTEGER NOT NULL DEFAULT 3,
        leased_by         TEXT,
        lease_expires_at  TEXT,
        heartbeat         TEXT,
        pages_found       INTEGER DEFAULT 0,
        sitemap_total     INTEGER DEFAULT 0,
        completeness_pct  REAL    DEFAULT 0,
        error             TEXT,
        created_at        TEXT    NOT NULL,
        updated_at        TEXT    NOT NULL,
        UNIQUE(run_id, municipality_id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS dev_sessions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        logged_at   TEXT    NOT NULL,
        hours       REAL    NOT NULL,
        note        TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS ssl_reports (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        municipality_id TEXT    NOT NULL,
        domain          TEXT    NOT NULL,
        grade           TEXT,
        cert_expiry     TEXT,
        ip_address      TEXT,
        has_warnings    INTEGER DEFAULT 0,
        checked_at      TEXT    NOT NULL,
        UNIQUE(municipality_id, domain)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS domain_expiry (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        municipality_id TEXT    NOT NULL,
        domain          TEXT    NOT NULL,
        registrar       TEXT,
        expiry_date     TEXT,
        creation_date   TEXT,
        checked_at      TEXT    NOT NULL,
        UNIQUE(municipality_id, domain)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS crawl_events (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER,
        task_id         INTEGER,
        municipality_id TEXT,
        level           TEXT    NOT NULL DEFAULT 'info',
        event           TEXT    NOT NULL,
        message         TEXT,
        meta            TEXT,
        created_at      TEXT    NOT NULL
    )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_municipality ON pages(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_municipality ON documents(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_diffs_municipality ON page_diffs(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_page_links_source ON page_links(source_url)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ssl_municipality ON ssl_reports(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain_municipality ON domain_expiry(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_tasks_run_status ON crawl_tasks(run_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_events_created ON crawl_events(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_events_run ON crawl_events(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_events_muni ON crawl_events(municipality_id)")


def _init_postgres(conn) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id              BIGSERIAL PRIMARY KEY,
        municipality_id TEXT      NOT NULL,
        url             TEXT      NOT NULL UNIQUE,
        content_type    TEXT,
        content_hash    TEXT,
        status_code     INTEGER,
        depth           INTEGER,
        last_crawled    TEXT      NOT NULL,
        title           TEXT,
        snippet         TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id              BIGSERIAL PRIMARY KEY,
        municipality_id TEXT      NOT NULL,
        url             TEXT      NOT NULL UNIQUE,
        file_type       TEXT,
        content_hash    TEXT,
        downloaded      INTEGER   DEFAULT 0,
        first_seen      TEXT      NOT NULL,
        last_seen       TEXT      NOT NULL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS page_diffs (
        id              BIGSERIAL PRIMARY KEY,
        municipality_id TEXT      NOT NULL,
        url             TEXT      NOT NULL,
        old_hash        TEXT,
        new_hash        TEXT,
        detected_at     TEXT      NOT NULL
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS crawl_runs (
        id                  BIGSERIAL PRIMARY KEY,
        started_at          TEXT      NOT NULL,
        finished_at         TEXT,
        municipalities      INTEGER   DEFAULT 0,
        pages_crawled       INTEGER   DEFAULT 0,
        pages_changed       INTEGER   DEFAULT 0,
        pages_new           INTEGER   DEFAULT 0,
        errors              INTEGER   DEFAULT 0,
        sitemap_urls_found  INTEGER   DEFAULT 0,
        completeness_pct    REAL      DEFAULT 0
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS page_links (
        id          BIGSERIAL PRIMARY KEY,
        source_url  TEXT NOT NULL,
        target_url  TEXT NOT NULL,
        UNIQUE(source_url, target_url)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS crawl_tasks (
        id                BIGSERIAL PRIMARY KEY,
        run_id            BIGINT  NOT NULL,
        municipality_id   TEXT    NOT NULL,
        mode              TEXT    NOT NULL DEFAULT 'discover',
        status            TEXT    NOT NULL DEFAULT 'pending',
        attempts          INTEGER NOT NULL DEFAULT 0,
        max_attempts      INTEGER NOT NULL DEFAULT 3,
        leased_by         TEXT,
        lease_expires_at  TEXT,
        heartbeat         TEXT,
        pages_found       INTEGER DEFAULT 0,
        sitemap_total     INTEGER DEFAULT 0,
        completeness_pct  REAL    DEFAULT 0,
        error             TEXT,
        created_at        TEXT    NOT NULL,
        updated_at        TEXT    NOT NULL,
        UNIQUE(run_id, municipality_id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS dev_sessions (
        id          BIGSERIAL PRIMARY KEY,
        logged_at   TEXT  NOT NULL,
        hours       REAL  NOT NULL,
        note        TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS ssl_reports (
        id              BIGSERIAL PRIMARY KEY,
        municipality_id TEXT      NOT NULL,
        domain          TEXT      NOT NULL,
        grade           TEXT,
        cert_expiry     TEXT,
        ip_address      TEXT,
        has_warnings    INTEGER   DEFAULT 0,
        checked_at      TEXT      NOT NULL,
        UNIQUE(municipality_id, domain)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS domain_expiry (
        id              BIGSERIAL PRIMARY KEY,
        municipality_id TEXT      NOT NULL,
        domain          TEXT      NOT NULL,
        registrar       TEXT,
        expiry_date     TEXT,
        creation_date   TEXT,
        checked_at      TEXT      NOT NULL,
        UNIQUE(municipality_id, domain)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS crawl_events (
        id              BIGSERIAL PRIMARY KEY,
        run_id          BIGINT,
        task_id         BIGINT,
        municipality_id TEXT,
        level           TEXT    NOT NULL DEFAULT 'info',
        event           TEXT    NOT NULL,
        message         TEXT,
        meta            TEXT,
        created_at      TEXT    NOT NULL
    )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_municipality ON pages(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_municipality ON documents(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_diffs_municipality ON page_diffs(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_page_links_source ON page_links(source_url)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ssl_municipality ON ssl_reports(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain_municipality ON domain_expiry(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_tasks_run_status ON crawl_tasks(run_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_events_created ON crawl_events(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_events_run ON crawl_events(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_events_muni ON crawl_events(municipality_id)")

    # Resync sequences in case rows were inserted with explicit IDs (e.g. after migration)
    for table in ["crawl_runs", "crawl_tasks", "crawl_events", "pages", "documents", "page_diffs", "page_links", "dev_sessions", "ssl_reports", "domain_expiry"]:
        conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"COALESCE(MAX(id), 0) + 1, false) FROM {table}"
        )


if __name__ == "__main__":
    init_db()
