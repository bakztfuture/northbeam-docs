"""Listing, viewing, restoring, and deleting an article's snapshots."""

import sqlite3

from app.errors import ArticleNotFoundError, DraftConflictError, SnapshotInUseError, SnapshotNotFoundError
from app.models import RestoreSnapshotRequest
from app.repositories import articles, queries
from app.repositories.database import write_txn
from app.repositories.queries import Row


def list_snapshots(conn: sqlite3.Connection, article_id: str) -> list[Row]:
    """Every snapshot, newest first. An unknown article is a 404, not an empty list."""
    if articles.get_article(conn, article_id) is None:
        raise ArticleNotFoundError()
    return articles.list_versions(conn, article_id)


def get_snapshot(conn: sqlite3.Connection, article_id: str, snapshot_id: str) -> Row:
    """A snapshot of another article is not found."""
    if articles.get_article(conn, article_id) is None:
        raise ArticleNotFoundError()
    snapshot = articles.get_version(conn, article_id, snapshot_id)
    if snapshot is None:
        raise SnapshotNotFoundError()
    return snapshot


def restore_snapshot(
    conn: sqlite3.Connection, article_id: str, snapshot_id: str, request: RestoreSnapshotRequest
) -> Row:
    """Copy a snapshot into the draft with compare-and-set. Never touches article_versions."""
    now = queries.utc_now()
    with write_txn(conn):
        snapshot = articles.get_version(conn, article_id, snapshot_id)
        if snapshot is None:
            if articles.get_article(conn, article_id) is None:
                raise ArticleNotFoundError()
            raise SnapshotNotFoundError()
        changed = articles.update_draft_if_version(
            conn,
            article_id,
            snapshot["title"],
            snapshot["body"],
            snapshot["tags"],
            request.expected_draft_version,
            now,
        )
        if not changed:
            # The article exists (its snapshot does), so the version was stale.
            raise DraftConflictError()
        return articles.get_article(conn, article_id)


def delete_snapshot(conn: sqlite3.Connection, article_id: str, snapshot_id: str) -> None:
    """Delete a snapshot the article does not point to. ON DELETE RESTRICT is the backstop for this check."""
    with write_txn(conn):
        article = articles.get_article(conn, article_id)
        if article is None:
            raise ArticleNotFoundError()
        if articles.get_version(conn, article_id, snapshot_id) is None:
            raise SnapshotNotFoundError()
        if article["current_published_version_id"] == snapshot_id:
            raise SnapshotInUseError()
        articles.delete_version(conn, article_id, snapshot_id)
