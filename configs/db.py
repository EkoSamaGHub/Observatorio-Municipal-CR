"""
Unified DB layer — SQLite for local dev, Postgres for production.

All SQL throughout the codebase uses Postgres-style placeholders:
  - Positional:  %s
  - Named:       %(key)s
  - Conflict:    ON CONFLICT DO NOTHING / ON CONFLICT(col) DO UPDATE

When the backend is SQLite these are transparently converted to ? and :key.
"""

import os
import re
import sqlite3
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "municipal.db"


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _to_sqlite(sql: str) -> str:
    """Translate Postgres placeholders → SQLite placeholders."""
    sql = re.sub(r"%\((\w+)\)s", r":\1", sql)
    sql = sql.replace("%s", "?")
    return sql


class _SQLiteCursor:
    def __init__(self, c: sqlite3.Cursor):
        self._c = c
        self._lastrowid: int | None = None

    def execute(self, sql: str, params=None):
        self._c.execute(_to_sqlite(sql), params or ())
        if "RETURNING" in sql.upper():
            row = self._c.fetchone()
            if row:
                self._lastrowid = list(dict(row).values())[0]
        else:
            self._lastrowid = self._c.lastrowid
        return self

    def executemany(self, sql: str, seq):
        self._c.executemany(_to_sqlite(sql), seq)
        return self

    def fetchone(self) -> dict | None:
        row = self._c.fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list[dict]:
        return [dict(r) for r in self._c.fetchall()]

    @property
    def lastrowid(self) -> int | None:
        return self._lastrowid


class _SQLiteConn:
    def __init__(self):
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._c = sqlite3.connect(_DB_PATH)
        self._c.row_factory = sqlite3.Row
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql: str, params=None) -> _SQLiteCursor:
        cur = _SQLiteCursor(self._c.cursor())
        return cur.execute(sql, params)

    def cursor(self) -> _SQLiteCursor:
        return _SQLiteCursor(self._c.cursor())

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()

    @property
    def total_changes(self) -> int:
        return self._c.total_changes


# ── Postgres connection pool ────────────────────────────────────────────────
#
# A process-wide bounded pool. Before this, every get_connection() opened a
# brand-new Postgres connection (each with a ~15s SSL handshake). Under load
# (parallel crawl workers + the API server-rendering pages) that exhausted
# Timescale's connection limit, the API's queries blocked waiting for a
# connection, SSR hung, and the site went down. The pool caps concurrent
# connections per process and reuses them, so a connection is always cheap.
#
# Created lazily (NOT at import) so it is never inherited across a fork — each
# worker/uvicorn process gets its own pool.

_pg_pool = None


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        from urllib.parse import urlparse, parse_qs

        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        r = urlparse(DATABASE_URL)
        qs = {k: v[0] for k, v in parse_qs(r.query).items()}
        conn_kwargs = dict(
            host=r.hostname,
            port=r.port or 5432,
            dbname=(r.path or "/tsdb").lstrip("/"),
            user=r.username,
            password=r.password,
            sslmode=qs.get("sslmode", "require"),
            connect_timeout=15,
            row_factory=dict_row,
        )
        _pg_pool = ConnectionPool(
            min_size=1,
            max_size=int(os.environ.get("DB_POOL_MAX", "4")),
            timeout=int(os.environ.get("DB_POOL_TIMEOUT", "20")),
            max_idle=60,
            kwargs=conn_kwargs,
            open=True,
        )
    return _pg_pool


# ── Postgres helpers ──────────────────────────────────────────────────────────

class _PgCursor:
    def __init__(self, c):
        self._c = c
        self._lastrowid: int | None = None

    def execute(self, sql: str, params=None):
        self._c.execute(sql, params or ())
        if "RETURNING" in sql.upper():
            row = self._c.fetchone()
            if row:
                self._lastrowid = list(row.values())[0]
        return self

    def executemany(self, sql: str, seq):
        self._c.executemany(sql, seq)
        return self

    def fetchone(self) -> dict | None:
        row = self._c.fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list[dict]:
        return [dict(r) for r in self._c.fetchall()]

    @property
    def lastrowid(self) -> int | None:
        return self._lastrowid


class _PgConn:
    def __init__(self):
        self._pool = _get_pg_pool()
        self._c = self._pool.getconn()

    def execute(self, sql: str, params=None) -> _PgCursor:
        cur = _PgCursor(self._c.cursor())
        return cur.execute(sql, params)

    def cursor(self) -> _PgCursor:
        return _PgCursor(self._c.cursor())

    def commit(self):
        self._c.commit()

    def close(self):
        # Return the connection to the pool instead of closing it. Roll back any
        # open transaction first so the next borrower starts clean (and any
        # FOR UPDATE locks are released).
        if self._c is None:
            return
        try:
            self._c.rollback()
        except Exception:
            pass
        try:
            self._pool.putconn(self._c)
        except Exception:
            try:
                self._c.close()
            except Exception:
                pass
        finally:
            self._c = None

    @property
    def total_changes(self) -> int:
        return 1  # psycopg2 doesn't expose this; return truthy


# ── Public API ────────────────────────────────────────────────────────────────

def get_connection() -> _SQLiteConn | _PgConn:
    if DATABASE_URL:
        return _PgConn()
    return _SQLiteConn()


BACKEND = "postgres" if DATABASE_URL else "sqlite"
