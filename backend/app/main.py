from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.errors import register_error_handlers
from app.repositories.database import try_init_db
from app.routes import api_router

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # A failed init is logged and recorded; the app still starts so every request
    # gets a clear 503 "Database unavailable", and get_db retries the init.
    try_init_db(app)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Northbeam Docs", lifespan=lifespan)
    app.state.settings = settings or Settings()
    app.state.db_ready = False
    register_error_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)
    return app


app = create_app()
