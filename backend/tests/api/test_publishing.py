from ..helpers import ARTICLES, create_article, get_article, publish, save_draft, unpublish


def snapshot_rows(db, article_id):
    return db.execute(
        "SELECT version_number, title, body, tags FROM article_versions WHERE article_id = ? ORDER BY version_number",
        (article_id,),
    ).fetchall()


# --- Publish ---


def test_first_publish_creates_v1_and_leaves_the_draft_alone(client):
    article = create_article(client, title="Getting Started", body="# Welcome", tags=["guide"])

    published = publish(client, article)

    assert set(published) == {"article", "snapshot"}
    snapshot = published["snapshot"]
    assert set(snapshot) == {"id", "versionNumber", "title", "body", "tags", "createdAt", "isCurrent"}
    assert snapshot["versionNumber"] == 1
    assert snapshot["isCurrent"] is True
    assert (snapshot["title"], snapshot["body"], snapshot["tags"]) == ("Getting Started", "# Welcome", ["guide"])

    after = published["article"]
    assert after == get_article(client, article["id"])
    assert after["status"] == "published"
    assert after["currentPublishedVersionId"] == snapshot["id"]
    assert after["publishedAt"] is not None
    assert after["draft"] == article["draft"]
    assert after["draftVersion"] == article["draftVersion"]
    assert after["updatedAt"] == article["updatedAt"]


def test_republish_creates_the_next_snapshot_and_keeps_published_at(client):
    first = publish(client, create_article(client))["article"]
    edited = save_draft(client, first, body="Edited")

    second = publish(client, edited)

    assert second["snapshot"]["versionNumber"] == 2
    assert second["snapshot"]["body"] == "Edited"
    assert second["article"]["currentPublishedVersionId"] == second["snapshot"]["id"]
    assert second["article"]["publishedAt"] == first["publishedAt"]


def test_publishing_unchanged_content_still_creates_a_snapshot(client, db):  # EC-22
    article = publish(client, create_article(client))["article"]

    publish(client, article)

    rows = [tuple(row) for row in snapshot_rows(db, article["id"])]
    assert [row[0] for row in rows] == [1, 2]
    assert rows[0][1:] == rows[1][1:]


def test_stale_publish_is_rejected_and_creates_no_snapshot(client, db):  # EC-02
    article = create_article(client)
    save_draft(client, article, body="Saved by another writer")

    response = client.post(f"{ARTICLES}/{article['id']}/publish", json={"expectedDraftVersion": 1})

    assert response.status_code == 409
    assert response.json()["title"] == "Draft conflict"
    after = get_article(client, article["id"])
    assert (after["status"], after["currentPublishedVersionId"], after["publishedAt"]) == ("draft", None, None)
    assert snapshot_rows(db, article["id"]) == []


# --- Unpublish ---


def test_unpublish_keeps_the_pointer_published_at_and_every_snapshot(client, db):  # EC-09
    first = publish(client, create_article(client))["article"]
    published = publish(client, first)["article"]

    unpublished = unpublish(client, published)

    assert unpublished["status"] == "unpublished"
    # Everything else, including the pointer and publishedAt, is exactly as before.
    assert {key: value for key, value in unpublished.items() if key != "status"} == {
        key: value for key, value in published.items() if key != "status"
    }
    assert len(snapshot_rows(db, published["id"])) == 2


def test_republish_after_unpublish(client):  # EC-21
    article = unpublish(client, publish(client, create_article(client))["article"])

    republished = publish(client, article)

    assert republished["snapshot"]["versionNumber"] == 2
    assert republished["article"]["status"] == "published"
    assert republished["article"]["currentPublishedVersionId"] == republished["snapshot"]["id"]
    assert republished["article"]["publishedAt"] == article["publishedAt"]


def test_unpublish_of_a_draft_only_article_is_rejected(client):  # EC-20
    article = create_article(client)

    response = client.post(f"{ARTICLES}/{article['id']}/unpublish")

    assert response.status_code == 409
    assert get_article(client, article["id"]) == article


def test_unpublish_twice_is_rejected(client):  # EC-30
    article = unpublish(client, publish(client, create_article(client))["article"])

    response = client.post(f"{ARTICLES}/{article['id']}/unpublish")

    assert response.status_code == 409
    assert get_article(client, article["id"]) == article
