"""The flat error format, the SQLite error mapping, and the generic 500."""

import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """A known application error, rendered as {"code", "title", "message"?}."""

    def __init__(self, code: int, title: str, message: str | None = None) -> None:
        super().__init__(title)
        self.code = code
        self.title = title
        self.message = message


def error_response(error: AppError) -> JSONResponse:
    body: dict[str, object] = {"code": error.code, "title": error.title}
    if error.message is not None:
        body["message"] = error.message
    return JSONResponse(status_code=error.code, content=body)


def internal_error_response() -> JSONResponse:
    return JSONResponse(status_code=500, content={"code": 500, "title": "Internal server error"})


def map_sqlite_error(exc: sqlite3.Error) -> AppError | None:
    """Map expected database failures to an AppError; None means it is a bug (500)."""
    text = str(exc)
    if isinstance(exc, sqlite3.IntegrityError):
        if text.startswith("UNIQUE constraint failed: articles.slug"):
            return AppError(409, "Slug already exists", "Another article already uses this slug.")
        if text.startswith("FOREIGN KEY constraint failed"):
            return AppError(409, "Snapshot is in use", "The article still points to this snapshot.")
    if isinstance(exc, sqlite3.OperationalError) and text.startswith(("database is locked", "database is busy")):
        return AppError(503, "Service temporarily unavailable", "The database is busy.")
    # CHECK and trigger aborts land here on purpose: the API never attempts those
    # writes, so reaching one means there is a bug, and a 409 would hide it.
    return None


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc)


async def sqlite_error_handler(request: Request, exc: sqlite3.Error) -> JSONResponse:
    mapped = map_sqlite_error(exc)
    if mapped is not None:
        return error_response(mapped)
    logger.error("Unexpected database error on %s %s", request.method, request.url.path, exc_info=exc)
    return internal_error_response()


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return internal_error_response()


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(sqlite3.Error, sqlite_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
