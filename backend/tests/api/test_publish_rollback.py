"""Mandatory (EC-03): a publish that fails after its snapshot is written leaves nothing behind."""

import sqlite3

from fastapi.testclient import TestClient

from app.repositories.database import connect, get_db

from ..helpers import ARTICLES, create_article, publish


class FailOnPublishUpdate:
    """A real connection that raises when it sees publish's article UPDATE, after the snapshot INSERT ran."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, *args):
        if sql.startswith("UPDATE articles SET status = 'published'"):
            raise sqlite3.OperationalError("simulated failure")
        return self._conn.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_failed_publish_rolls_back_completely(app, client, db, settings):
    article = publish(client, create_article(client))["article"]
    before = dict(db.execute("SELECT * FROM articles WHERE id = ?", (article["id"],)).fetchone())

    def failing_db():
        conn = connect(settings)
        try:
            yield FailOnPublishUpdate(conn)
        finally:
            conn.close()

    app.dependency_overrides[get_db] = failing_db
    # The simulated error is unexpected, so it reaches the generic 500 handler, which
    # TestClient would otherwise re-raise into the test.
    with TestClient(app, raise_server_exceptions=False) as failing_client:
        response = failing_client.post(f"{ARTICLES}/{article['id']}/publish", json={"expectedDraftVersion": 1})
    del app.dependency_overrides[get_db]

    assert response.status_code == 500
    assert response.json() == {"code": 500, "title": "Internal server error"}
    assert db.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 1
    assert dict(db.execute("SELECT * FROM articles WHERE id = ?", (article["id"],)).fetchone()) == before

    assert publish(client, article)["snapshot"]["versionNumber"] == 2
