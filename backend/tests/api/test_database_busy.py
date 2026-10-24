"""EC-19: a write that cannot get the lock within the busy timeout is a 503, not a hang or a partial change."""

from app.repositories.database import connect

from ..helpers import ARTICLES, create_article, get_article, save_draft


def test_lock_exhaustion_is_a_503_and_saves_work_once_the_lock_is_released(client, settings):
    article = create_article(client)
    holder = connect(settings)  # another writer that holds the write lock
    holder.execute("BEGIN IMMEDIATE")
    try:
        response = client.patch(
            f"{ARTICLES}/{article['id']}/draft",
            json={"title": "T", "body": "Blocked", "tags": [], "expectedDraftVersion": 1},
        )

        assert response.status_code == 503
        assert response.json() == {
            "code": 503,
            "title": "Service temporarily unavailable",
            "message": "The database is busy.",
        }
        assert "retry-after" not in response.headers
        assert get_article(client, article["id"]) == article  # reads still work while the lock is held
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert save_draft(client, article, body="After the lock")["draftVersion"] == 2
