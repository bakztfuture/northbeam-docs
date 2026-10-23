"""One article through its whole life, in the order a writer would actually work (design Decision 7).

After every step it checks what readers see, the history, the pointer, and published_at. It also checks
draft_version and updated_at: both change on create, save, and restore, and neither changes on publish,
unpublish, or delete.
"""

from ..helpers import (
    PUBLIC_ARTICLES,
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


def test_one_article_from_create_to_republish(client, ticking_clock):
    def history():
        return [item["versionNumber"] for item in list_snapshots(client, article["id"])]

    def public_body():
        response = read_public(client, article["slug"])
        return response.json()["body"] if response.status_code == 200 else response.status_code

    def assert_draft_changed(before, after):
        assert after["draftVersion"] == before["draftVersion"] + 1
        assert after["updatedAt"] > before["updatedAt"]

    def assert_draft_untouched(before, after):
        assert (after["draftVersion"], after["updatedAt"]) == (before["draftVersion"], before["updatedAt"])

    # Create: hidden from readers, no history yet.
    article = create_article(client, body="Draft 1")
    assert article["draftVersion"] == 1
    assert public_body() == 404
    assert history() == []

    # Save twice: draft version 1 -> 2 -> 3; still hidden, still no snapshots.
    for body in ("Draft 2", "Draft 3"):
        saved = save_draft(client, article, body=body)
        assert_draft_changed(article, saved)
        article = saved
    assert article["draftVersion"] == 3
    assert public_body() == 404
    assert history() == []

    # Publish v1: readers see it; published_at is set; the pointer names v1.
    published = publish(client, article)
    v1 = published["snapshot"]
    assert_draft_untouched(article, published["article"])
    article = published["article"]
    first_published_at = article["publishedAt"]
    assert first_published_at is not None
    assert article["currentPublishedVersionId"] == v1["id"]
    assert public_body() == "Draft 3"
    assert history() == [1]

    # Save a new draft: readers still see v1.
    saved = save_draft(client, article, body="Draft 4")
    assert_draft_changed(article, saved)
    article = saved
    assert public_body() == "Draft 3"

    # Publish v2: readers see v2; published_at is unchanged.
    published = publish(client, article)
    v2 = published["snapshot"]
    assert_draft_untouched(article, published["article"])
    article = published["article"]
    assert article["publishedAt"] == first_published_at
    assert public_body() == "Draft 4"
    assert history() == [2, 1]

    # Delete v1: 204; history is v2 only; readers still see v2.
    assert delete_snapshot(client, article["id"], v1["id"]).status_code == 204
    assert_draft_untouched(article, get_article(client, article["id"]))
    assert history() == [2]
    assert public_body() == "Draft 4"

    # Unpublish: hidden again, and gone from the public list; the pointer and published_at stay.
    unpublished = unpublish(client, article)
    assert_draft_untouched(article, unpublished)
    article = unpublished
    assert public_body() == 404
    assert client.get(PUBLIC_ARTICLES).json() == []
    assert (article["currentPublishedVersionId"], article["publishedAt"]) == (v2["id"], first_published_at)
    assert history() == [2]

    # Restore v2 into the draft: the draft equals v2; still unpublished; no snapshot created.
    restored = restore(client, article, v2["id"])
    assert_draft_changed(article, restored)
    article = restored
    assert article["draft"]["body"] == "Draft 4"
    assert article["status"] == "unpublished"
    assert history() == [2]

    # Delete v2: refused, since the pointer still names it.
    assert delete_snapshot(client, article["id"], v2["id"]).status_code == 409
    assert history() == [2]

    # Publish v3: readers see it; published_at unchanged; numbered 3, not reusing 1.
    published = publish(client, article)
    assert_draft_untouched(article, published["article"])
    article = published["article"]
    assert published["snapshot"]["versionNumber"] == 3
    assert article["publishedAt"] == first_published_at
    assert public_body() == "Draft 4"

    # Delete v2: allowed now that the pointer has moved.
    assert delete_snapshot(client, article["id"], v2["id"]).status_code == 204
    assert_draft_untouched(article, get_article(client, article["id"]))
    assert history() == [3]
