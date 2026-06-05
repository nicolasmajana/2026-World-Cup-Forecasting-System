"""Database connection pool for the FastAPI backend."""

import os
from contextlib import contextmanager
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

_pool: SimpleConnectionPool | None = None


def init_pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(1, 10, DATABASE_URL)


@contextmanager
def get_cursor():
    """Yield a RealDictCursor; returns rows as dicts."""
    init_pool()
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    finally:
        _pool.putconn(conn)
