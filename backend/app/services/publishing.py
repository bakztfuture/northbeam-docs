"""Publishing the saved draft as a new snapshot, and unpublishing."""

import sqlite3
import uuid

from app.errors import ArticleNotFoundError, ArticleNotPublishedError, DraftConflictError
from app.models import PublishArticleRequest
from app.repositories import articles, queries
from app.repositories.database import write_txn
from app.repositories.queries import Row


def publish_article(conn: sqlite3.Connection, article_id: str, request: PublishArticleRequest) -> tuple[Row, Row]:
    """One transaction: check the version, INSERT the snapshot, then point the article at it.

    Returns (article, snapshot). The INSERT must come first: the composite FK needs the
    snapshot to exist before the article can point at it.
    """
    snapshot_id = str(uuid.uuid4())
    now = queries.utc_now()
    with write_txn(conn):
        article = articles.get_article(conn, article_id)
        if article is None:
            raise ArticleNotFoundError()
        if article["draft_version"] != request.expected_draft_version:
            raise DraftConflictError()
        number = article["last_published_version_number"] + 1
        articles.insert_version(
            conn,
            snapshot_id,
            article_id,
            number,
            article["draft_title"],
            article["draft_body"],
            article["draft_tags"],
            now,
        )
        articles.set_published(conn, article_id, snapshot_id, number, now)
        return articles.get_article(conn, article_id), articles.get_version(conn, article_id, snapshot_id)


def unpublish_article(conn: sqlite3.Connection, article_id: str) -> Row:
    with write_txn(conn):
        if not articles.set_unpublished(conn, article_id):
            # Nothing matched: either the article is missing, or it was not published.
            if articles.get_article(conn, article_id) is None:
                raise ArticleNotFoundError()
            raise ArticleNotPublishedError()
        return articles.get_article(conn, article_id)
