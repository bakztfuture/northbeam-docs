"""Direct inserts for database tests, until the publish endpoint exists (group 2)."""

import sqlite3
import uuid

NOW = "2026-01-01T00:00:00.000Z"


def insert_article(conn: sqlite3.Connection, slug: str = "getting-started", **columns) -> str:
    article_id = columns.pop("id", str(uuid.uuid4()))
    row = {
        "id": article_id,
        "slug": slug,
        "draft_title": "Getting Started",
        "draft_body": "# Welcome",
        "draft_tags": '["guide"]',
        "created_at": NOW,
        "updated_at": NOW,
        **columns,
    }
    names = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO articles ({names}) VALUES ({placeholders})", tuple(row.values()))
    return article_id


def insert_snapshot(conn: sqlite3.Connection, article_id: str, number: int) -> str:
    snapshot_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO article_versions (id, article_id, version_number, title, body, tags, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (snapshot_id, article_id, number, f"Title v{number}", f"Body v{number}", '["guide"]', NOW),
    )
    return snapshot_id


def point_at(conn: sqlite3.Connection, article_id: str, snapshot_id: str, number: int) -> None:
    conn.execute(
        "UPDATE articles SET status = 'published', current_published_version_id = ?,"
        " last_published_version_number = ?, published_at = COALESCE(published_at, ?) WHERE id = ?",
        (snapshot_id, number, NOW, article_id),
    )


def seed_published_article(conn: sqlite3.Connection, slug: str = "getting-started") -> tuple[str, str, str]:
    """A published article with a historical snapshot v1 and a live snapshot v2. Returns (article, v1, v2) ids."""
    article_id = insert_article(conn, slug)
    v1 = insert_snapshot(conn, article_id, 1)
    v2 = insert_snapshot(conn, article_id, 2)
    point_at(conn, article_id, v2, 2)
    return article_id, v1, v2
