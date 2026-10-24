"""Writer (admin) endpoints, mounted under /api/admin. HTTP only: each route parses the request,
calls one service function, and returns the response model.

    Authoring    create, list, and get articles; save the draft   -> services/authoring.py
    Publishing   publish and unpublish                            -> services/publishing.py
    History      list, view, restore, and delete snapshots        -> services/history.py
"""

import sqlite3
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.models import (
    AdminArticle,
    ArticleListItem,
    CreateArticleRequest,
    PublishArticleRequest,
    PublishedArticle,
    RestoreSnapshotRequest,
    SaveDraftRequest,
    Snapshot,
    SnapshotListItem,
)
from app.repositories.database import get_db
from app.services import authoring, history, publishing

router = APIRouter()


# --- Authoring ---


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


# --- Publishing ---


@router.post("/articles/{article_id}/publish", response_model=PublishedArticle, status_code=201)
def publish_article(
    article_id: UUID, request: PublishArticleRequest, conn: sqlite3.Connection = Depends(get_db)
) -> PublishedArticle:
    article, snapshot = publishing.publish_article(conn, str(article_id), request)
    return PublishedArticle(
        article=AdminArticle.from_row(article),
        snapshot=Snapshot.from_row(snapshot),
    )


@router.post("/articles/{article_id}/unpublish", response_model=AdminArticle)
def unpublish_article(article_id: UUID, conn: sqlite3.Connection = Depends(get_db)) -> AdminArticle:
    return AdminArticle.from_row(publishing.unpublish_article(conn, str(article_id)))


# --- History ---


@router.get("/articles/{article_id}/snapshots", response_model=list[SnapshotListItem])
def list_snapshots(article_id: UUID, conn: sqlite3.Connection = Depends(get_db)) -> list[SnapshotListItem]:
    return [SnapshotListItem.from_row(snapshot) for snapshot in history.list_snapshots(conn, str(article_id))]


@router.get("/articles/{article_id}/snapshots/{snapshot_id}", response_model=Snapshot)
def get_snapshot(article_id: UUID, snapshot_id: UUID, conn: sqlite3.Connection = Depends(get_db)) -> Snapshot:
    return Snapshot.from_row(history.get_snapshot(conn, str(article_id), str(snapshot_id)))


@router.post("/articles/{article_id}/snapshots/{snapshot_id}/restore", response_model=AdminArticle)
def restore_snapshot(
    article_id: UUID, snapshot_id: UUID, request: RestoreSnapshotRequest, conn: sqlite3.Connection = Depends(get_db)
) -> AdminArticle:
    return AdminArticle.from_row(history.restore_snapshot(conn, str(article_id), str(snapshot_id), request))


@router.delete("/articles/{article_id}/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(article_id: UUID, snapshot_id: UUID, conn: sqlite3.Connection = Depends(get_db)) -> Response:
    history.delete_snapshot(conn, str(article_id), str(snapshot_id))
    return Response(status_code=204)
