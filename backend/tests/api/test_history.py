from ..helpers import (
    ARTICLES,
    create_article,
    delete_snapshot,
    get_article,
    list_snapshots,
    publish,
    read_public,
    restore,
    save_draft,
    unpublish,
)

UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


def published_three_times(client, slug="getting-started"):
    """An article published as v1, v2, and v3 (bodies "Body v1".."Body v3"), with v3 live."""
    article = create_article(client, slug=slug)
    snapshots = []
    for number in (1, 2, 3):
        article = save_draft(client, article, body=f"Body v{number}")
        published = publish(client, article)
        article, snapshot = published["article"], published["snapshot"]
        snapshots.append(snapshot)
    return article, snapshots


def numbers(client, article_id):
    return [item["versionNumber"] for item in list_snapshots(client, article_id)]


# --- List ---


def test_list_is_newest_first_and_marks_the_current_snapshot(client):
    article, _ = published_three_times(client)

    items = list_snapshots(client, article["id"])

    assert all(set(item) == {"id", "versionNumber", "title", "createdAt", "isCurrent"} for item in items)
    assert [item["versionNumber"] for item in items] == [3, 2, 1]
    assert [item["isCurrent"] for item in items] == [True, False, False]


def test_list_for_a_draft_only_article_is_empty(client):
    article = create_article(client)

    assert list_snapshots(client, article["id"]) == []


def test_list_for_an_unknown_article_is_404(client):
    response = client.get(f"{ARTICLES}/{UNKNOWN_ID}/snapshots")

    assert response.status_code == 404
    assert response.json() == {"code": 404, "title": "Article not found"}


# --- View ---


def test_view_returns_the_snapshot_not_the_later_draft(client):
    article = publish(client, create_article(client, body="Original"))["article"]
    save_draft(client, article, body="Edited later")

    response = client.get(f"{ARTICLES}/{article['id']}/snapshots/{article['currentPublishedVersionId']}")

    assert response.status_code == 200
    snapshot = response.json()
    assert set(snapshot) == {"id", "versionNumber", "title", "body", "tags", "createdAt", "isCurrent"}
    assert (snapshot["versionNumber"], snapshot["body"], snapshot["isCurrent"]) == (1, "Original", True)


def test_snapshot_of_another_article_or_missing_is_404(client):  # EC-17
    article = publish(client, create_article(client, slug="mine"))["article"]
    other = publish(client, create_article(client, slug="other"))["snapshot"]

    for snapshot_id in (other["id"], UNKNOWN_ID):
        base = f"{ARTICLES}/{article['id']}/snapshots/{snapshot_id}"
        responses = [
            client.get(base),
            client.post(f"{base}/restore", json={"expectedDraftVersion": article["draftVersion"]}),
            client.delete(base),
        ]
        for response in responses:
            assert response.status_code == 404
            assert response.json() == {"code": 404, "title": "Snapshot not found"}

    assert get_article(client, article["id"]) == article
    assert len(list_snapshots(client, article["id"])) == 1


# --- Restore ---


def test_restore_copies_the_snapshot_into_the_draft_only(client, ticking_clock):  # EC-11
    article, (v1, _, _) = published_three_times(client)
    history_before = list_snapshots(client, article["id"])

    restored = restore(client, article, v1["id"])

    assert set(restored) == set(article)
    assert restored["draft"] == {"title": v1["title"], "body": v1["body"], "tags": v1["tags"]}
    assert restored["draftVersion"] == article["draftVersion"] + 1
    assert restored["updatedAt"] > article["updatedAt"]
    unchanged = ("status", "currentPublishedVersionId", "publishedAt", "createdAt", "slug")
    assert {key: restored[key] for key in unchanged} == {key: article[key] for key in unchanged}
    assert list_snapshots(client, article["id"]) == history_before
    assert read_public(client, article["slug"]).json()["body"] == "Body v3"


def test_stale_restore_is_a_draft_conflict(client):  # EC-12
    article, (v1, _, _) = published_three_times(client)
    save_draft(client, article, body="Saved by another writer")

    response = client.post(
        f"{ARTICLES}/{article['id']}/snapshots/{v1['id']}/restore",
        json={"expectedDraftVersion": article["draftVersion"]},
    )

    assert response.status_code == 409
    assert response.json()["title"] == "Draft conflict"
    assert get_article(client, article["id"])["draft"]["body"] == "Saved by another writer"


def test_restore_then_publish_creates_a_new_snapshot(client):  # EC-32
    article, (v1, _, _) = published_three_times(client)

    republished = publish(client, restore(client, article, v1["id"]))

    assert republished["snapshot"]["versionNumber"] == 4
    assert republished["snapshot"]["id"] != v1["id"]
    assert republished["snapshot"]["body"] == v1["body"]
    assert republished["article"]["currentPublishedVersionId"] == republished["snapshot"]["id"]


# --- Delete ---


def test_delete_a_historical_snapshot(client):  # EC-08
    article, (v1, _, _) = published_three_times(client)

    response = delete_snapshot(client, article["id"], v1["id"])

    assert response.status_code == 204
    assert response.content == b""
    assert numbers(client, article["id"]) == [3, 2]
    assert get_article(client, article["id"]) == article


def test_delete_the_live_snapshot_is_rejected(client):  # EC-07
    article, (_, _, v3) = published_three_times(client)

    response = delete_snapshot(client, article["id"], v3["id"])

    assert response.status_code == 409
    assert response.json()["title"] == "Snapshot is in use"
    assert numbers(client, article["id"]) == [3, 2, 1]
    assert read_public(client, article["slug"]).json()["body"] == "Body v3"


def test_delete_the_pointed_to_snapshot_while_unpublished_is_rejected(client):  # EC-10
    article, (_, _, v3) = published_three_times(client)
    unpublish(client, article)

    response = delete_snapshot(client, article["id"], v3["id"])

    assert response.status_code == 409
    assert numbers(client, article["id"]) == [3, 2, 1]


def test_delete_a_historical_snapshot_while_unpublished(client):  # EC-42
    article, (v1, _, v3) = published_three_times(client)
    article = unpublish(client, article)

    response = delete_snapshot(client, article["id"], v1["id"])

    assert response.status_code == 204
    assert numbers(client, article["id"]) == [3, 2]
    after = get_article(client, article["id"])
    assert (after["status"], after["currentPublishedVersionId"]) == ("unpublished", v3["id"])


def test_republishing_frees_the_previously_pointed_to_snapshot(client):  # EC-31
    article, (_, _, v3) = published_three_times(client)
    article = publish(client, unpublish(client, article))["article"]

    response = delete_snapshot(client, article["id"], v3["id"])

    assert response.status_code == 204
    assert numbers(client, article["id"]) == [4, 2, 1]


def test_numbers_are_never_reused_after_deletes(client):  # EC-13
    article, (v1, v2, _) = published_three_times(client)
    delete_snapshot(client, article["id"], v1["id"])
    delete_snapshot(client, article["id"], v2["id"])

    republished = publish(client, article)

    assert republished["snapshot"]["versionNumber"] == 4
    assert numbers(client, article["id"]) == [4, 3]
