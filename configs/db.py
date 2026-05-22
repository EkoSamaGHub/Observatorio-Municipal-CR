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
    def __init__(self, url: str):
        import psycopg2
        import psycopg2.extras
        from urllib.parse import urlparse, parse_qs
        r = urlparse(url)
        qs = {k: v[0] for k, v in parse_qs(r.query).items()}
        self._c = psycopg2.connect(
            host=r.hostname,
            port=r.port,
            dbname=(r.path or "/tsdb").lstrip("/"),
            user=r.username,
            password=r.password,
            sslmode=qs.get("sslmode", "prefer"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )

    def execute(self, sql: str, params=None) -> _PgCursor:
        cur = _PgCursor(self._c.cursor())
        return cur.execute(sql, params)

    def cursor(self) -> _PgCursor:
        return _PgCursor(self._c.cursor())

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()

    @property
    def total_changes(self) -> int:
        return 1  # psycopg2 doesn't expose this; return truthy


# ── Public API ────────────────────────────────────────────────────────────────

def get_connection() -> _SQLiteConn | _PgConn:
    if DATABASE_URL:
        return _PgConn(DATABASE_URL)
    return _SQLiteConn()


BACKEND = "postgres" if DATABASE_URL else "sqlite"
