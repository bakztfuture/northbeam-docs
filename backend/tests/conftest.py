import sqlite3
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories.database import connect, init_db


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(db_path=tmp_path / "docs.sqlite3", busy_timeout_ms=100)


@pytest.fixture
def app(settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(settings) -> Iterator[sqlite3.Connection]:
    """A plain connection to an initialized test database, for tests about the database itself."""
    conn = connect(settings)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()
