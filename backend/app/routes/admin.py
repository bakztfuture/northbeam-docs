import sqlite3
from uuid import UUID

from fastapi import APIRouter, Depends

from app.models import (
    AdminArticle,
    ArticleListItem,
    CreateArticleRequest,
    PublishArticleRequest,
    PublishedArticle,
    SaveDraftRequest,
    Snapshot,
)
from app.repositories.database import get_db
from app.services import authoring, publishing

router = APIRouter()


@router.post("/articles", response_model=AdminArticle, status_code=201)
def create_article(request: CreateArticleRequest, conn: sqlite3.Connection = Depends(get_db)) -> AdminArticle:
    return AdminArticle.from_row(authoring.create_article(conn, request))


@router.get("/articles", response_model=list[ArticleListItem])
def list_articles(conn: sqlite3.Connection = Depends(get_db)) -> list[ArticleListItem]:
    return [ArticleListItem.from_row(article) for article in authoring.list_articles(conn)]


@router.get("/articles/{article_id}", response_model=AdminArticle)
def get_article(article_id: UUID, conn: sqlite3.Connection = Depends(get_db)) -> AdminArticle:
    return AdminArticle.from_row(authoring.get_article(conn, str(article_id)))


@router.patch("/articles/{article_id}/draft", response_model=AdminArticle)
def save_draft(article_id: UUID, request: SaveDraftRequest, conn: sqlite3.Connection = Depends(get_db)) -> AdminArticle:
    return AdminArticle.from_row(authoring.save_draft(conn, str(article_id), request))


@router.post("/articles/{article_id}/publish", response_model=PublishedArticle, status_code=201)
def publish_article(
    article_id: UUID, request: PublishArticleRequest, conn: sqlite3.Connection = Depends(get_db)
) -> PublishedArticle:
    article, snapshot = publishing.publish_article(conn, str(article_id), request)
    return PublishedArticle(
        article=AdminArticle.from_row(article),
        snapshot=Snapshot.from_row(snapshot, article["current_published_version_id"]),
    )


@router.post("/articles/{article_id}/unpublish", response_model=AdminArticle)
def unpublish_article(article_id: UUID, conn: sqlite3.Connection = Depends(get_db)) -> AdminArticle:
    return AdminArticle.from_row(publishing.unpublish_article(conn, str(article_id)))
