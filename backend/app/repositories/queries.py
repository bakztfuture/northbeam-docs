"""Small helpers for writing SQL in the repository modules: fetch rows as dicts, insert from a dict,
delete with required conditions, and run a write that reports how many rows it changed. They never open transactions."""

import sqlite3
from datetime import UTC, datetime
from typing import Any

Row = dict[str, Any]


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Row | None:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else dict(row)


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[Row]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def insert(conn: sqlite3.Connection, table: str, row: Row) -> None:
    """INSERT one row from {column: value}, so each value sits next to its column.

    Values are always bound as parameters; `table` and the column names must come from code, never from a request.
    """
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(row.values()))


def delete(conn: sqlite3.Connection, table: str, where: Row) -> int:
    """DELETE the rows matching every {column: value} in `where`. Returns the number of rows deleted.

    `where` must not be empty, so a call can never delete a whole table. Values are always bound as
    parameters; `table` and the column names must come from code, never from a request.
    """
    if not where:
        raise ValueError("delete() needs at least one condition")
    conditions = " AND ".join(f"{column} = ?" for column in where)
    return conn.execute(f"DELETE FROM {table} WHERE {conditions}", tuple(where.values())).rowcount


def execute(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    """Run one write statement and return how many rows it changed."""
    return conn.execute(sql, params).rowcount


# --- Util ---


def utc_now() -> str:
    """Util: the current time for timestamp columns, UTC ISO 8601 with milliseconds (sorts correctly as text)."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
