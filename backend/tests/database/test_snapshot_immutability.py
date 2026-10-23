"""Mandatory (EC-05): the database itself rejects any change to a snapshot, live or historical."""

import sqlite3

import pytest

from ..helpers import create_article, publish


def test_direct_update_of_live_and_historical_snapshots_is_rejected(client, db):
    historical = publish(client, create_article(client))
    live = publish(client, historical["article"])
    rows_before = db.execute("SELECT * FROM article_versions ORDER BY version_number").fetchall()

    for snapshot in (live["snapshot"], historical["snapshot"]):
        with pytest.raises(sqlite3.IntegrityError, match="Published snapshots are immutable"):
            db.execute("UPDATE article_versions SET body = 'changed' WHERE id = ?", (snapshot["id"],))

    rows_after = db.execute("SELECT * FROM article_versions ORDER BY version_number").fetchall()
    assert [tuple(row) for row in rows_after] == [tuple(row) for row in rows_before]
