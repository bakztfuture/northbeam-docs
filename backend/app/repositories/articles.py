"""SQL for articles and article_versions.

Each function takes a connection and returns rows (as dicts, with tags decoded) or a count.
None of them opens a transaction or raises HTTP errors; services do both.
"""

import json
import sqlite3

from app.repositories.queries import Row, execute, fetch_all, fetch_one, insert


def _parse_tags_on_article(article: Row | None) -> Row | None:
    if article is not None:
        article["draft_tags"] = json.loads(article["draft_tags"])
    return article


def _parse_tags_on_version(version: Row | None) -> Row | None:
    if version is not None:
        version["tags"] = json.loads(version["tags"])
    return version


def get_article(conn: sqlite3.Connection, article_id: str) -> Row | None:
    return _parse_tags_on_article(fetch_one(conn, "SELECT * FROM articles WHERE id = ?", (article_id,)))


def slug_exists(conn: sqlite3.Connection, slug: str) -> bool:
    return fetch_one(conn, "SELECT 1 FROM articles WHERE slug = ?", (slug,)) is not None


def list_articles(conn: sqlite3.Connection) -> list[Row]:
    return [
        _parse_tags_on_article(article)
        for article in fetch_all(conn, "SELECT * FROM articles ORDER BY updated_at DESC, id")
    ]


def insert_article(
    conn: sqlite3.Connection, article_id: str, slug: str, title: str, body: str, tags: list[str], now: str
) -> None:
    insert(
        conn,
        "articles",
        {
            "id": article_id,
            "slug": slug,
            "draft_title": title,
            "draft_body": body,
            "draft_tags": json.dumps(tags),
            "created_at": now,
            "updated_at": now,
        },
    )


def update_draft_if_version(
    conn: sqlite3.Connection,
    article_id: str,
    title: str,
    body: str,
    tags: list[str],
    expected_draft_version: int,
    now: str,
) -> int:
    """Compare-and-set: replace the draft only if its version still matches. Returns the number of rows changed."""
    return execute(
        conn,
        "UPDATE articles SET draft_title = ?, draft_body = ?, draft_tags = ?,"
        " draft_version = draft_version + 1, updated_at = ?"
        " WHERE id = ? AND draft_version = ?",
        (title, body, json.dumps(tags), now, article_id, expected_draft_version),
    )


def insert_version(
    conn: sqlite3.Connection,
    version_id: str,
    article_id: str,
    version_number: int,
    title: str,
    body: str,
    tags: list[str],
    now: str,
) -> None:
    insert(
        conn,
        "article_versions",
        {
            "id": version_id,
            "article_id": article_id,
            "version_number": version_number,
            "title": title,
            "body": body,
            "tags": json.dumps(tags),
            "created_at": now,
        },
    )


def get_version(conn: sqlite3.Connection, article_id: str, version_id: str) -> Row | None:
    return _parse_tags_on_version(
        fetch_one(conn, "SELECT * FROM article_versions WHERE id = ? AND article_id = ?", (version_id, article_id))
    )


def set_published(conn: sqlite3.Connection, article_id: str, version_id: str, version_number: int, now: str) -> None:
    """Point the article at a new snapshot. Leaves the draft, draft_version, and updated_at alone."""
    execute(
        conn,
        "UPDATE articles SET status = 'published', current_published_version_id = ?,"
        " last_published_version_number = ?, published_at = COALESCE(published_at, ?)"
        " WHERE id = ?",
        (version_id, version_number, now, article_id),
    )


def set_unpublished(conn: sqlite3.Connection, article_id: str) -> int:
    """Status-only change, and only from 'published'. Returns the number of rows changed."""
    return execute(
        conn, "UPDATE articles SET status = 'unpublished' WHERE id = ? AND status = 'published'", (article_id,)
    )
