"""Pydantic models for the API's JSON, in two groups:

- Requests (input): bodies the API accepts. They validate and normalize input. Names end in `Request`.
- Responses (output): bodies the API returns. Routes set them as `response_model`, so only the
  listed fields are ever sent. Names are the thing returned (`AdminArticle`, `Snapshot`). Each one
  that is built from database rows has a `from_row` that maps the columns to its fields. Fields are
  plain types: the request rules checked the data on the way in, and are not re-run on the way out.

JSON is camelCase; Python attributes are snake_case.
"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from app.repositories.queries import Row


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# --- Requests (input) ---

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_SLUG_LENGTH = 100
MAX_TITLE_LENGTH = 200
MAX_BODY_LENGTH = 50_000
MAX_TAGS = 20
MAX_TAG_LENGTH = 100


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must contain at least one non-whitespace character")
    return value


def _normalize_tags(tags: list[str]) -> list[str]:
    """Trim and lowercase each tag, reject blank or overlong ones, and drop duplicates in first-seen order."""
    normalized: list[str] = []
    for raw in tags:
        tag = raw.strip().lower()
        if not tag:
            raise ValueError("tags must not be blank")
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(f"each tag must be at most {MAX_TAG_LENGTH} characters")
        if tag not in normalized:
            normalized.append(tag)
    return normalized


Slug = Annotated[str, Field(min_length=1, max_length=MAX_SLUG_LENGTH, pattern=SLUG_PATTERN)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH)]
Body = Annotated[str, Field(max_length=MAX_BODY_LENGTH), AfterValidator(_require_non_blank)]
Tags = Annotated[list[str], Field(max_length=MAX_TAGS), AfterValidator(_normalize_tags)]
DraftVersion = Annotated[int, Field(ge=1)]


class CreateArticleRequest(CamelModel):
    title: Title
    slug: Slug
    body: Body
    tags: Tags = Field(default_factory=list)


class SaveDraftRequest(CamelModel):
    # Unknown fields, such as a stray `slug`, are a 422 rather than silently ignored.
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    title: Title
    body: Body
    tags: Tags = Field(default_factory=list)
    expected_draft_version: DraftVersion


class PublishArticleRequest(CamelModel):
    expected_draft_version: DraftVersion


class RestoreSnapshotRequest(CamelModel):
    expected_draft_version: DraftVersion


# --- Responses (output) ---

ArticleStatus = Literal["draft", "published", "unpublished"]


class Draft(CamelModel):
    title: str
    body: str
    tags: list[str]


class AdminArticle(CamelModel):
    id: UUID
    slug: str
    status: ArticleStatus
    draft: Draft
    draft_version: int
    current_published_version_id: UUID | None  # null until the first publish
    published_at: str | None  # null until the first publish
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, article: Row) -> Self:
        return cls(
            id=article["id"],
            slug=article["slug"],
            status=article["status"],
            draft=Draft(title=article["draft_title"], body=article["draft_body"], tags=article["draft_tags"]),
            draft_version=article["draft_version"],
            current_published_version_id=article["current_published_version_id"],
            published_at=article["published_at"],
            created_at=article["created_at"],
            updated_at=article["updated_at"],
        )


class ArticleListItem(CamelModel):
    id: UUID
    slug: str
    title: str  # the draft title
    status: ArticleStatus
    updated_at: str

    @classmethod
    def from_row(cls, article: Row) -> Self:
        return cls(
            id=article["id"],
            slug=article["slug"],
            title=article["draft_title"],
            status=article["status"],
            updated_at=article["updated_at"],
        )


class Snapshot(CamelModel):
    id: UUID
    version_number: int
    title: str
    body: str
    tags: list[str]
    created_at: str
    is_current: bool  # true for the snapshot the article points to

    @classmethod
    def from_row(cls, snapshot: Row, current_published_version_id: str | None) -> Self:
        return cls(
            id=snapshot["id"],
            version_number=snapshot["version_number"],
            title=snapshot["title"],
            body=snapshot["body"],
            tags=snapshot["tags"],
            created_at=snapshot["created_at"],
            is_current=snapshot["id"] == current_published_version_id,
        )


class PublishedArticle(CamelModel):
    article: AdminArticle
    snapshot: Snapshot  # the new snapshot


class HealthStatus(CamelModel):
    status: Literal["ok"]
