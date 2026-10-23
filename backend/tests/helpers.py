"""Shortcuts for setting up articles through the HTTP API."""

from fastapi.testclient import TestClient

ARTICLES = "/api/admin/articles"
PUBLIC_ARTICLES = "/api/public/articles"


def create_article(client: TestClient, slug: str = "getting-started", **fields) -> dict:
    body = {"title": "Getting Started", "slug": slug, "body": "# Welcome", "tags": ["guide"], **fields}
    response = client.post(ARTICLES, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def save_draft(client: TestClient, article: dict, **fields) -> dict:
    body = {
        "title": article["draft"]["title"],
        "body": article["draft"]["body"],
        "tags": article["draft"]["tags"],
        "expectedDraftVersion": article["draftVersion"],
        **fields,
    }
    response = client.patch(f"{ARTICLES}/{article['id']}/draft", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def publish(client: TestClient, article: dict) -> dict:
    """Publish with the article's current draft version. Returns the PublishedArticle body."""
    response = client.post(
        f"{ARTICLES}/{article['id']}/publish", json={"expectedDraftVersion": article["draftVersion"]}
    )
    assert response.status_code == 201, response.text
    return response.json()


def unpublish(client: TestClient, article: dict) -> dict:
    response = client.post(f"{ARTICLES}/{article['id']}/unpublish")
    assert response.status_code == 200, response.text
    return response.json()


def get_article(client: TestClient, article_id: str) -> dict:
    response = client.get(f"{ARTICLES}/{article_id}")
    assert response.status_code == 200, response.text
    return response.json()


def list_snapshots(client: TestClient, article_id: str) -> list[dict]:
    response = client.get(f"{ARTICLES}/{article_id}/snapshots")
    assert response.status_code == 200, response.text
    return response.json()


def restore(client: TestClient, article: dict, snapshot_id: str) -> dict:
    """Restore with the article's current draft version. Returns the AdminArticle body."""
    response = client.post(
        f"{ARTICLES}/{article['id']}/snapshots/{snapshot_id}/restore",
        json={"expectedDraftVersion": article["draftVersion"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def delete_snapshot(client: TestClient, article_id: str, snapshot_id: str):
    return client.delete(f"{ARTICLES}/{article_id}/snapshots/{snapshot_id}")


def read_public(client: TestClient, slug: str):
    return client.get(f"{PUBLIC_ARTICLES}/{slug}")
