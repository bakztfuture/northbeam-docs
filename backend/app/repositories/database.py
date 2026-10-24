"""Connections, transactions, and schema setup. The only module that opens SQLite connections."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from app.config import Settings
from app.errors import AppError, DatabaseBusyError, DatabaseUnavailableError, SlugTakenError, SnapshotInUseError

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


def _map_sqlite_error(exc: sqlite3.Error) -> AppError | None:
    """The expected database failures, as AppErrors; None means it is a bug (500)."""
    text = str(exc)
    if isinstance(exc, sqlite3.IntegrityError):
        if text.startswith("UNIQUE constraint failed: articles.slug"):
            return SlugTakenError()
        if text.startswith("FOREIGN KEY constraint failed"):
            return SnapshotInUseError()
    if isinstance(exc, sqlite3.OperationalError) and text.startswith(("database is locked", "database is busy")):
        return DatabaseBusyError()
    # CHECK and trigger aborts land here on purpose: the API never attempts those
    # writes, so reaching one means there is a bug, and a 409 would hide it.
    return None


@contextmanager
def write_txn(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """The one place write transactions begin: BEGIN IMMEDIATE, then COMMIT.

    On any exception: ROLLBACK, then raise the matching AppError for an expected
    SQLite failure, or re-raise anything else unchanged.
    """
    try:
        conn.execute("BEGIN IMMEDIATE")  # inside the try: this is where a busy lock fails
        yield conn
        conn.execute("COMMIT")
    except BaseException as exc:
        # SQLite may already have rolled back on its own (for example after SQLITE_FULL).
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        if isinstance(exc, sqlite3.Error) and (mapped := _map_sqlite_error(exc)):
            raise mapped from exc
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


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, and the single 'database unavailable' gate."""
    app = request.app
    if not app.state.db_ready and not try_init_db(app):
        raise DatabaseUnavailableError()
    try:
        conn = connect(app.state.settings)
    except (sqlite3.Error, OSError):
        logger.exception("Could not open the database at %s", app.state.settings.db_path)
        raise DatabaseUnavailableError() from None
    try:
        yield conn
    finally:
        conn.close()
