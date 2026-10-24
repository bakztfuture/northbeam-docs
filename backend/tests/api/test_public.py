from ..helpers import PUBLIC_ARTICLES, create_article, publish, read_public, save_draft, unpublish

PUBLIC_ARTICLE_FIELDS = {"slug", "title", "body", "tags", "publishedAt"}
PUBLIC_LIST_ITEM_FIELDS = {"slug", "title", "tags", "publishedAt"}


# --- List ---


def test_list_shows_only_published_articles(client):
    create_article(client, slug="draft-slug")
    publish(client, create_article(client, slug="published-slug"))
    unpublish(client, publish(client, create_article(client, slug="unpublished-slug"))["article"])

    items = client.get(PUBLIC_ARTICLES).json()

    assert [item["slug"] for item in items] == ["published-slug"]
    assert set(items[0]) == PUBLIC_LIST_ITEM_FIELDS


def test_list_shows_the_snapshot_not_saved_draft_edits(client):
    article = publish(client, create_article(client, title="Live title", tags=["live"]))["article"]
    save_draft(client, article, title="Draft title", tags=["draft"])

    (item,) = client.get(PUBLIC_ARTICLES).json()

    assert (item["title"], item["tags"]) == ("Live title", ["live"])


def test_list_is_newest_first_by_first_publication_time(client, ticking_clock):
    a = publish(client, create_article(client, slug="a"))["article"]
    publish(client, create_article(client, slug="b"))
    republished_a = publish(client, a)["article"]  # republishing does not move A up

    items = client.get(PUBLIC_ARTICLES).json()

    assert [item["slug"] for item in items] == ["b", "a"]
    assert items[1]["publishedAt"] == a["publishedAt"] == republished_a["publishedAt"]


# --- Read ---


def test_read_returns_the_live_snapshot_not_the_draft(client):  # EC-06
    article = publish(client, create_article(client, title="Live", body="Live body", tags=["live"]))["article"]
    save_draft(client, article, title="Draft", body="Draft body", tags=["draft"])

    response = read_public(client, article["slug"])

    assert response.status_code == 200
    assert response.json() == {
        "slug": article["slug"],
        "title": "Live",
        "body": "Live body",
        "tags": ["live"],
        "publishedAt": article["publishedAt"],
    }
    assert set(response.json()) == PUBLIC_ARTICLE_FIELDS


def test_read_shows_new_content_after_a_republish(client):
    article = publish(client, create_article(client, body="First"))["article"]
    publish(client, save_draft(client, article, body="Second"))

    assert read_public(client, article["slug"]).json()["body"] == "Second"


# --- Hidden articles ---


def test_draft_only_unpublished_and_unknown_slugs_get_the_same_404(client):  # EC-09, EC-14, EC-15, EC-23, EC-37
    create_article(client, slug="draft-slug")
    unpublish(client, publish(client, create_article(client, slug="unpublished-slug"))["article"])

    responses = [read_public(client, slug) for slug in ("draft-slug", "unpublished-slug", "no-such-slug")]

    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"code": 404, "title": "Article not found"}
    assert client.get(PUBLIC_ARTICLES).json() == []
