"""Database connection helpers."""

from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row


def database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("PG_DSN") or ""
    if not url:
        raise RuntimeError("DATABASE_URL (or PG_DSN) is not configured")
    return url


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), row_factory=dict_row)
