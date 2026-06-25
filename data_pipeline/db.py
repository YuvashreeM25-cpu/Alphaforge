"""
Database layer with TWO backends:

  * SQLite  (default, zero-setup — the "download and run" path)
  * Postgres (set DATABASE_URL=postgresql://user:pass@host:5432/db)

A thin adapter gives both backends an identical API so the rest of the code
never branches on backend. Application code always writes `?` placeholders and
calls `conn.execute / executemany / executescript / upsert`; the adapter rewrites
SQL per dialect. Rows are dict-accessible (`row["close"]`) on both.
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

DB_PATH = Path(os.environ.get("ALPHAFORGE_DB",
                              Path(__file__).resolve().parent.parent / "alphaforge.db"))

_AUTO_PK = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS companies (
    ticker     TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    sector     TEXT NOT NULL,
    shares_out REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL NOT NULL,
    volume REAL,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker     TEXT NOT NULL,
    period     TEXT NOT NULL,
    revenue    REAL, ebitda REAL, net_income REAL, fcf REAL,
    total_debt REAL, cash REAL, equity REAL,
    source     TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, period)
);
CREATE TABLE IF NOT EXISTS runs (
    id {_AUTO_PK},
    question   TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS theses (
    id {_AUTO_PK},
    run_id INTEGER NOT NULL,
    ticker TEXT,
    body   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest_log (
    id {_AUTO_PK},
    run_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    source  TEXT,
    ok      INTEGER,
    failed  INTEGER,
    detail  TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id {_AUTO_PK},
    fired_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ticker   TEXT,
    rule     TEXT,
    value    REAL,
    message  TEXT
);
"""


def _to_pg(sql: str) -> str:
    """Rewrite `?` placeholders to `%s` for psycopg."""
    return re.sub(r"\?", "%s", sql)


class _Conn:
    """Uniform wrapper over a sqlite3 or psycopg connection."""

    def __init__(self, raw, is_pg: bool):
        self._raw = raw
        self._pg = is_pg

    def execute(self, sql, params=()):
        cur = self._raw.cursor()
        cur.execute(_to_pg(sql) if self._pg else sql, params)
        return cur

    def executemany(self, sql, seq):
        cur = self._raw.cursor()
        cur.executemany(_to_pg(sql) if self._pg else sql, seq)
        return cur

    def executescript(self, script):
        if self._pg:
            cur = self._raw.cursor()
            for stmt in [s.strip() for s in script.split(";") if s.strip()]:
                cur.execute(stmt)
        else:
            self._raw.executescript(script)

    def upsert(self, table, row: dict, conflict_cols):
        """Dialect-aware INSERT ... ON CONFLICT (used by live ingestion)."""
        cols = list(row.keys())
        ph = ", ".join("?" * len(cols))
        col_sql = ", ".join(cols)
        updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c not in conflict_cols)
        conflict = ", ".join(conflict_cols)
        if self._pg:
            sql = (f"INSERT INTO {table} ({col_sql}) VALUES ({ph}) "
                   f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}")
        else:
            sql = (f"INSERT INTO {table} ({col_sql}) VALUES ({ph}) "
                   f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}")
        self.execute(sql, tuple(row[c] for c in cols))

    @property
    def lastrowid(self):
        return getattr(self, "_lastrowid", None)

    def insert_returning_id(self, sql, params=()):
        """INSERT and return the new row id, on both backends."""
        if self._pg:
            cur = self.execute(sql.rstrip().rstrip(";") + " RETURNING id", params)
            return cur.fetchone()["id"]
        cur = self.execute(sql, params)
        return cur.lastrowid

    def read_df(self, sql, params=()):
        """Return a pandas DataFrame (handles placeholder dialect)."""
        import pandas as pd
        return pd.read_sql_query(_to_pg(sql) if self._pg else sql, self._raw,
                                 params=params or None)

    @property
    def raw(self):
        return self._raw

    def commit(self):
        self._raw.commit()


@contextmanager
def connect():
    if IS_PG:
        import psycopg
        from psycopg.rows import dict_row
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        conn = _Conn(raw, True)
        try:
            yield conn
            raw.commit()
        finally:
            raw.close()
    else:
        import sqlite3
        raw = sqlite3.connect(DB_PATH)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON;")
        conn = _Conn(raw, False)
        try:
            yield conn
            raw.commit()
        finally:
            raw.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def reset_db() -> None:
    if not IS_PG and DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


def backend() -> str:
    return "postgres" if IS_PG else "sqlite"


if __name__ == "__main__":
    init_db()
    print(f"Initialized {backend()} database"
          + (f" at {DB_PATH}" if not IS_PG else ""))
