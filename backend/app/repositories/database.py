"""Connections, transactions, and schema setup. The only module that opens SQLite connections."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from app.config import Settings
from app.errors import AppError

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "migrations" / "0001_initial_schema.sql"


def connect(settings: Settings) -> sqlite3.Connection:
    """Open a connection with autocommit (no implicit transactions) and the required pragmas."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        settings.db_path,
        isolation_level=None,
        timeout=settings.busy_timeout_ms / 1000,
        check_same_thread=False,
    )
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(settings.busy_timeout_ms)}")
        conn.execute("PRAGMA synchronous = FULL")
    except BaseException:
        conn.close()
        raise
    return conn


@contextmanager
def write_txn(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """The one place write transactions begin: BEGIN IMMEDIATE, then COMMIT, or ROLLBACK and re-raise."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        # SQLite may already have rolled back on its own (for example after SQLITE_FULL).
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def init_db(conn: sqlite3.Connection) -> None:
    """Switch the file to WAL mode and apply the initial schema in one transaction. Safe to re-run."""
    conn.execute("PRAGMA journal_mode = WAL")
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    # executescript() cannot run inside write_txn (it would commit the open transaction
    # first), so the script carries its own BEGIN IMMEDIATE / COMMIT.
    try:
        conn.executescript(f"BEGIN IMMEDIATE;\n{schema}\nCOMMIT;")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def try_init_db(app: FastAPI) -> bool:
    """Run init_db() against the configured file and record the outcome in app.state.db_ready."""
    try:
        conn = connect(app.state.settings)
        try:
            init_db(conn)
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        logger.exception("Database initialization failed for %s", app.state.settings.db_path)
        app.state.db_ready = False
    else:
        app.state.db_ready = True
    return app.state.db_ready


def _database_unavailable() -> AppError:
    return AppError(503, "Database unavailable", "The database could not be opened.")


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, and the single 'database unavailable' gate."""
    app = request.app
    if not app.state.db_ready and not try_init_db(app):
        raise _database_unavailable()
    try:
        conn = connect(app.state.settings)
    except (sqlite3.Error, OSError):
        logger.exception("Could not open the database at %s", app.state.settings.db_path)
        raise _database_unavailable() from None
    try:
        yield conn
    finally:
        conn.close()
