"""Shared FastAPI dependencies."""

import sqlite3
from collections.abc import Iterator

from app.db.connection import get_connection


def db() -> Iterator[sqlite3.Connection]:
    """One SQLite connection per request.

    Not a module-level singleton: FastAPI runs sync endpoints in a thread pool,
    and a sqlite3 connection belongs to the thread that created it. Connections
    are cheap here (a local file plus the sqlite-vec extension load) and this
    keeps each request's transaction isolated.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
