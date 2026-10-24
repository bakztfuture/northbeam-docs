"""Every known error, in one place, plus the handlers that render them and the generic 500."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for every known error, rendered as {"code", "title", "message"?}."""

    code = 500
    title = "Internal server error"
    message: str | None = None

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message or self.title)


class ArticleNotFoundError(AppError):
    code = 404
    title = "Article not found"


class SnapshotNotFoundError(AppError):  # also for a snapshot that belongs to another article
    code = 404
    title = "Snapshot not found"


class DraftConflictError(AppError):
    code = 409
    title = "Draft conflict"
    message = "The draft changed since it was loaded. Reload it and try again."


class SlugTakenError(AppError):
    code = 409
    title = "Slug already exists"
    message = "Another article already uses this slug."


class ArticleNotPublishedError(AppError):
    code = 409
    title = "Article is not published"
    message = "Only a published article can be unpublished."


class SnapshotInUseError(AppError):  # every FK failure maps here; SQLite does not say which reference failed
    code = 409
    title = "Snapshot is in use"
    message = "The article still points to this snapshot."


class DatabaseBusyError(AppError):  # the write lock was not available within the busy timeout
    code = 503
    title = "Service temporarily unavailable"
    message = "The database is busy."


class DatabaseUnavailableError(AppError):  # the database could not be opened at all
    code = 503
    title = "Database unavailable"
    message = "The database could not be opened."


def error_response(error: AppError) -> JSONResponse:
    body: dict[str, object] = {"code": error.code, "title": error.title}
    if error.message is not None:
        body["message"] = error.message
    return JSONResponse(status_code=error.code, content=body)


def internal_error_response() -> JSONResponse:
    return JSONResponse(status_code=500, content={"code": 500, "title": "Internal server error"})


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return internal_error_response()


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
