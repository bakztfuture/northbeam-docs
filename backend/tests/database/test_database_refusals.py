"""Writes the API never makes, which the specs say the database itself must reject."""

import sqlite3

import pytest

from ..helpers import create_article, publish


def test_published_article_without_a_pointer_is_rejected(client, db):
    article = create_article(client)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        db.execute(
            "UPDATE articles SET status = 'published', published_at = '2026-01-01T00:00:00.000Z' WHERE id = ?",
            (article["id"],),
        )


def test_pointer_to_another_articles_snapshot_is_rejected(client, db):  # EC-28
    other = publish(client, create_article(client, slug="other"))
    mine = publish(client, create_article(client, slug="mine"))

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        db.execute(
            "UPDATE articles SET current_published_version_id = ? WHERE id = ?",
            (other["snapshot"]["id"], mine["article"]["id"]),
        )


def test_deleting_the_pointed_to_snapshot_is_rejected(client, db):
    live = publish(client, create_article(client))["snapshot"]

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        db.execute("DELETE FROM article_versions WHERE id = ?", (live["id"],))

    assert db.execute("SELECT COUNT(*) FROM article_versions WHERE id = ?", (live["id"],)).fetchone()[0] == 1
