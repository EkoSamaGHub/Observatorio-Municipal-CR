from configs.db import get_connection, BACKEND

_DB_PATH_MSG = "TigerData cloud (Postgres)" if BACKEND == "postgres" else "local SQLite"


def _exec(conn, sql: str) -> None:
    conn.execute(sql)


def init_db() -> None:
    conn = get_connection()

    if BACKEND == "postgres":
        _init_postgres(conn)
    else:
        _init_sqlite(conn)

    conn.commit()
    conn.close()
    print(f"Database initialized — backend: {_DB_PATH_MSG}")


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
        last_crawled    TEXT    NOT NULL
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

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_municipality ON pages(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_municipality ON documents(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_diffs_municipality ON page_diffs(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_page_links_source ON page_links(source_url)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ssl_municipality ON ssl_reports(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain_municipality ON domain_expiry(municipality_id)")


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
        last_crawled    TEXT      NOT NULL
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

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_municipality ON pages(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_municipality ON documents(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_diffs_municipality ON page_diffs(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_page_links_source ON page_links(source_url)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ssl_municipality ON ssl_reports(municipality_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain_municipality ON domain_expiry(municipality_id)")

    # Resync sequences in case rows were inserted with explicit IDs (e.g. after migration)
    for table in ["crawl_runs", "pages", "documents", "page_diffs", "page_links", "dev_sessions", "ssl_reports", "domain_expiry"]:
        conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"COALESCE(MAX(id), 0) + 1, false) FROM {table}"
        )


if __name__ == "__main__":
    init_db()
