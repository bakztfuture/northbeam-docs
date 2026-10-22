"""Pydantic models for the API's JSON, in two groups:

- Requests (input): bodies the API accepts. They validate and normalize input. Names end in `Request`.
- Responses (output): bodies the API returns. Routes set them as `response_model`, so only the
  listed fields are ever sent. Names are the thing returned (`AdminArticle`, `Snapshot`);

JSON is camelCase; Python attributes are snake_case.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel


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


class HealthStatus(CamelModel):
    status: Literal["ok"]
