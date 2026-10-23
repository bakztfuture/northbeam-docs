from itertools import count

from app.repositories import queries

from ..helpers import ARTICLES, create_article, get_article, publish, save_draft, unpublish

ADMIN_ARTICLE_FIELDS = {
    "id",
    "slug",
    "status",
    "draft",
    "draftVersion",
    "currentPublishedVersionId",
    "publishedAt",
    "createdAt",
    "updatedAt",
}


# --- Create ---


def test_create_gives_a_draft_at_version_1_with_no_snapshot(client, db):
    article = create_article(client, title="Getting Started", body="# Welcome", tags=["guide"])

    assert set(article) == ADMIN_ARTICLE_FIELDS
    assert article["slug"] == "getting-started"
    assert article["status"] == "draft"
    assert article["draft"] == {"title": "Getting Started", "body": "# Welcome", "tags": ["guide"]}
    assert article["draftVersion"] == 1
    assert article["currentPublishedVersionId"] is None
    assert article["publishedAt"] is None
    assert article["createdAt"] == article["updatedAt"]
    assert get_article(client, article["id"]) == article
    assert db.execute("SELECT COUNT(*) FROM article_versions").fetchone()[0] == 0


def test_duplicate_slug_is_rejected(client):  # EC-16
    create_article(client, slug="getting-started")

    response = client.post(ARTICLES, json={"title": "Again", "slug": "getting-started", "body": "x"})

    assert response.status_code == 409
    assert response.json()["title"] == "Slug already exists"
    assert len(client.get(ARTICLES).json()) == 1


def test_invalid_create_returns_the_framework_422(client):  # EC-18
    response = client.post(ARTICLES, json={"title": "Getting Started", "slug": "Getting Started!", "body": "x"})

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "string_pattern_mismatch",
                "loc": ["body", "slug"],
                "msg": "String should match pattern '^[a-z0-9]+(-[a-z0-9]+)*$'",
                "input": "Getting Started!",
                "ctx": {"pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"},
            }
        ]
    }
    assert client.get(ARTICLES).json() == []


# --- List ---


def test_writer_admin_list_returns_all_status_types(client):
    # Unlike the public list, the writer's list must show every article, whatever its status.
    create_article(client, slug="draft-slug")
    publish(client, create_article(client, slug="published-slug"))
    unpublish(client, publish(client, create_article(client, slug="unpublished-slug"))["article"])

    items = client.get(ARTICLES).json()

    assert {item["slug"]: item["status"] for item in items} == {
        "draft-slug": "draft",
        "published-slug": "published",
        "unpublished-slug": "unpublished",
    }
    assert all(set(item) == {"id", "slug", "title", "status", "updatedAt"} for item in items)


def test_list_is_newest_updated_first_and_publishing_does_not_reorder_it(client, monkeypatch):
    # A clock that ticks once per call, so every write gets a distinct time.
    ticks = count()
    monkeypatch.setattr(queries, "utc_now", lambda: f"2026-01-01T00:00:{next(ticks):02d}.000Z")
    a = create_article(client, slug="a")
    b = create_article(client, slug="b")
    save_draft(client, a, title="A edited")

    def slugs():
        return [item["slug"] for item in client.get(ARTICLES).json()]

    assert slugs() == ["a", "b"]

    publish(client, b)
    assert slugs() == ["a", "b"]
    unpublish(client, b)
    assert slugs() == ["a", "b"]


# --- Get ---


def test_unknown_article_is_404(client):
    response = client.get(f"{ARTICLES}/00000000-0000-4000-8000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"code": 404, "title": "Article not found"}


# --- Save draft ---


def test_save_replaces_the_draft_and_increments_the_version(client):
    article = create_article(client)

    saved = save_draft(client, article, title="New title", body="New body", tags=["api"])

    assert set(saved) == ADMIN_ARTICLE_FIELDS
    assert saved["draft"] == {"title": "New title", "body": "New body", "tags": ["api"]}
    assert saved["draftVersion"] == 2
    assert saved["updatedAt"] > article["updatedAt"]
    assert saved["status"] == "draft"


def test_stale_save_is_a_draft_conflict(client):  # EC-01
    article = create_article(client)
    save_draft(client, article, body="First writer")

    response = client.patch(
        f"{ARTICLES}/{article['id']}/draft",
        json={"title": "T", "body": "Second writer", "tags": [], "expectedDraftVersion": 1},
    )

    assert response.status_code == 409
    assert response.json()["title"] == "Draft conflict"
    current = get_article(client, article["id"])
    assert current["draft"]["body"] == "First writer"
    assert current["draftVersion"] == 2


def test_save_with_a_slug_is_rejected(client):  # EC-36
    article = create_article(client, slug="getting-started")

    response = client.patch(
        f"{ARTICLES}/{article['id']}/draft",
        json={"title": "T", "body": "B", "tags": [], "expectedDraftVersion": 1, "slug": "renamed"},
    )

    assert response.status_code == 422
    assert get_article(client, article["id"]) == article
