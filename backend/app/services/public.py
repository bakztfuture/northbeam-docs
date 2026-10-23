"""What anonymous readers can see: published articles, from their live snapshot only."""

import sqlite3

from app.errors import ArticleNotFoundError
from app.repositories import articles
from app.repositories.queries import Row


def list_public_articles(conn: sqlite3.Connection) -> list[Row]:
    return articles.list_public_articles(conn)


def get_public_article(conn: sqlite3.Connection, slug: str) -> Row:
    # Draft-only, unpublished, and unknown slugs all get this same 404, so none can be told apart.
    article = articles.get_public_article(conn, slug)
    if article is None:
        raise ArticleNotFoundError()
    return article
