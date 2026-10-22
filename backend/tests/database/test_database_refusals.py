"""Writes the API never makes, which the specs say the database itself must reject."""

import sqlite3

import pytest

from .seed import insert_article, point_at, seed_published_article


def test_published_article_without_a_pointer_is_rejected(db):
    article_id = insert_article(db)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        db.execute(
            "UPDATE articles SET status = 'published', published_at = '2026-01-01T00:00:00.000Z' WHERE id = ?",
            (article_id,),
        )


def test_pointer_to_another_articles_snapshot_is_rejected(db):  # EC-28
    _, _, other_articles_snapshot = seed_published_article(db, slug="other")
    article_id = insert_article(db, slug="mine")

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        point_at(db, article_id, other_articles_snapshot, 1)


def test_deleting_the_pointed_to_snapshot_is_rejected(db):
    _, _, live = seed_published_article(db)

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        db.execute("DELETE FROM article_versions WHERE id = ?", (live,))

    assert db.execute("SELECT COUNT(*) FROM article_versions WHERE id = ?", (live,)).fetchone()[0] == 1
