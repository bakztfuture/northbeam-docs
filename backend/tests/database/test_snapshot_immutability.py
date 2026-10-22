"""Mandatory (EC-05): the database itself rejects any change to a snapshot, live or historical."""

import sqlite3

import pytest

from .seed import seed_published_article


def test_direct_update_of_live_and_historical_snapshots_is_rejected(db):
    _, historical, live = seed_published_article(db)
    rows_before = db.execute("SELECT * FROM article_versions ORDER BY version_number").fetchall()

    for snapshot_id in (live, historical):
        with pytest.raises(sqlite3.IntegrityError, match="Published snapshots are immutable"):
            db.execute("UPDATE article_versions SET body = 'changed' WHERE id = ?", (snapshot_id,))

    rows_after = db.execute("SELECT * FROM article_versions ORDER BY version_number").fetchall()
    assert [tuple(row) for row in rows_after] == [tuple(row) for row in rows_before]
