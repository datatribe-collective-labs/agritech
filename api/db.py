"""Database access: one read-only connection per request."""

from typing import Iterator

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from api import config


def make_engine() -> Engine:
    return create_engine(config.database_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)


def get_connection(request: Request) -> Iterator[Connection]:
    with request.app.state.engine.connect() as conn:
        yield conn


def table(name: str, schema: str) -> str:
    """Schema-qualified table name. An empty schema gives the bare name (used by the tests)."""
    return f"{schema}.{name}" if schema else name


def rows(conn: Connection, sql: str, **params) -> list:
    """Runs a query and returns every row as a dict."""
    return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def first(conn: Connection, sql: str, **params):
    found = rows(conn, sql, **params)
    return found[0] if found else None
