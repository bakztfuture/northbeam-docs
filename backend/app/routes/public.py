import sqlite3

from fastapi import APIRouter, Depends

from app.models import PublicArticle, PublicArticleListItem
from app.repositories.database import get_db
from app.services import public

router = APIRouter()


@router.get("/articles", response_model=list[PublicArticleListItem])
def list_public_articles(conn: sqlite3.Connection = Depends(get_db)) -> list[PublicArticleListItem]:
    return [PublicArticleListItem.from_row(article) for article in public.list_public_articles(conn)]


@router.get("/articles/{slug}", response_model=PublicArticle)
def get_public_article(slug: str, conn: sqlite3.Connection = Depends(get_db)) -> PublicArticle:
    # The slug is not format-validated: a malformed slug is just an unknown one (404, never 422).
    return PublicArticle.from_row(public.get_public_article(conn, slug))
