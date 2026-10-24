"""EC-29: everything written before a restart is there, unchanged, after it."""

from fastapi.testclient import TestClient

from app.main import create_app

from ..helpers import ARTICLES, PUBLIC_ARTICLES, create_article, list_snapshots, publish, save_draft


def test_data_survives_a_restart(settings):
    def snapshot_of_everything(client, article_id):
        return {
            "article": client.get(f"{ARTICLES}/{article_id}").json(),
            "history": list_snapshots(client, article_id),
            "public": client.get(PUBLIC_ARTICLES).json(),
        }

    with TestClient(create_app(settings)) as first:
        article = publish(first, create_article(first))["article"]
        save_draft(first, article, body="Unpublished edit")
        before = snapshot_of_everything(first, article["id"])

    with TestClient(create_app(settings)) as second:  # a new app instance on the same file
        assert snapshot_of_everything(second, article["id"]) == before
