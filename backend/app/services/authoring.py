"""Creating articles and saving drafts."""

import sqlite3
import uuid

from app.errors import ArticleNotFoundError, DraftConflictError, SlugTakenError
from app.models import CreateArticleRequest, SaveDraftRequest
from app.repositories import articles, queries
from app.repositories.database import write_txn
from app.repositories.queries import Row


def create_article(conn: sqlite3.Connection, request: CreateArticleRequest) -> Row:
    article_id = str(uuid.uuid4())
    now = queries.utc_now()
    with write_txn(conn):
        # The UNIQUE(slug) constraint is the backstop for a race past this check (mapped in write_txn).
        if articles.slug_exists(conn, request.slug):
            raise SlugTakenError()
        articles.insert_article(conn, article_id, request.slug, request.title, request.body, request.tags, now)
        return articles.get_article(conn, article_id)


def list_articles(conn: sqlite3.Connection) -> list[Row]:
    return articles.list_articles(conn)


def get_article(conn: sqlite3.Connection, article_id: str) -> Row:
    article = articles.get_article(conn, article_id)
    if article is None:
        raise ArticleNotFoundError()
    return article


def save_draft(conn: sqlite3.Connection, article_id: str, request: SaveDraftRequest) -> Row:
    now = queries.utc_now()
    with write_txn(conn):
        changed = articles.update_draft_if_version(
            conn, article_id, request.title, request.body, request.tags, request.expected_draft_version, now
        )
        if not changed:
            # Nothing matched: either the article is missing, or the version was stale.
            if articles.get_article(conn, article_id) is None:
                raise ArticleNotFoundError()
            raise DraftConflictError()
        return articles.get_article(conn, article_id)
