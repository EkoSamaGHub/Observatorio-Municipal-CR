import sqlite3
from typing import Generator

from configs.init_db import get_connection


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
